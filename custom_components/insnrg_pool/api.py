"""Client for the Insnrg third-party control API.

This is the API the Insnrg app exposes once "Voice Control" is enabled under
Connected Systems. Unlike the app's own Cognito-backed API it accepts a plain
username/password login and, crucially, supports writes.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    CMD_URL,
    LOGIN_URL,
    NS_MODE,
    NS_POWER,
    NS_TEMPERATURE,
    NS_THERMOSTAT,
    NS_TOGGLE,
)

_LOGGER = logging.getLogger(__name__)

# Refresh the token this many seconds before it actually expires.
_TOKEN_LEEWAY = 60
# Used when the token carries no readable `exp` claim.
_TOKEN_FALLBACK_TTL = 3000

_SWITCH_COMMANDS = {"ON": "TurnOn", "OFF": "TurnOff", "TIMER": "TimerOn"}


class InsnrgError(Exception):
    """Base error for the Insnrg API."""


class InsnrgAuthError(InsnrgError):
    """Raised when credentials are rejected."""


class InsnrgConnectionError(InsnrgError):
    """Raised when the API is unreachable or returns an unexpected status."""


class InsnrgVoiceControlDisabled(InsnrgError):
    """Raised when the account authenticates but exposes no devices.

    The third-party API returns an empty device list until Voice Control is
    enabled in the Insnrg app under Connected Systems.
    """


def _jwt_expiry(token: str) -> float:
    """Return the `exp` claim of a JWT, or a conservative fallback."""
    fallback = time.time() + _TOKEN_FALLBACK_TTL
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, binascii.Error, json.JSONDecodeError):
        _LOGGER.debug("Could not decode token expiry; using fallback TTL")
        return fallback
    exp = claims.get("exp")
    return float(exp) if isinstance(exp, (int, float)) else fallback


class InsnrgClient:
    """Authenticated client for a single Insnrg account."""

    def __init__(self, session: ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._user_id: str | None = None
        self.system_id: str | None = None
        self.address: str | None = None

    @property
    def user_id(self) -> str | None:
        """Return the account's user id, if logged in."""
        return self._user_id

    async def async_login(self) -> dict[str, Any]:
        """Authenticate and cache the session token. Returns the raw payload."""
        try:
            resp = await self._session.post(
                LOGIN_URL,
                json={"userName": self._username, "password": self._password},
            )
        except (ClientError, asyncio.TimeoutError) as err:
            raise InsnrgConnectionError(f"Could not reach Insnrg: {err}") from err

        if resp.status in (400, 401, 403):
            raise InsnrgAuthError("Insnrg rejected the username or password")
        if resp.status != 200:
            raise InsnrgConnectionError(f"Insnrg login returned HTTP {resp.status}")

        data = await resp.json(content_type=None)
        token = (data.get("auth") or {}).get("idToken")
        user_id = (data.get("user") or {}).get("userId")
        if not token or not user_id:
            raise InsnrgAuthError("Insnrg login response did not contain a token")

        self._token = token
        self._token_expires_at = _jwt_expiry(token)
        self._user_id = user_id

        devices = data.get("devices") or []
        if devices:
            self.system_id = devices[0].get("serial")
            self.address = devices[0].get("address")

        return data

    async def _async_token(self) -> str:
        """Return a valid token, logging in again if the cached one is stale."""
        async with self._lock:
            if self._token is None or time.time() >= self._token_expires_at - _TOKEN_LEEWAY:
                await self.async_login()
            assert self._token is not None
            return self._token

    async def _async_cmd(self, body: dict[str, Any]) -> Any:
        """Send a command, retrying once against a fresh token on 401/403."""
        for attempt in (1, 2):
            token = await self._async_token()
            payload = {**body, "userId": self._user_id}
            try:
                resp = await self._session.post(
                    CMD_URL,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )
            except (ClientError, asyncio.TimeoutError) as err:
                raise InsnrgConnectionError(f"Could not reach Insnrg: {err}") from err

            if resp.status in (401, 403) and attempt == 1:
                # Force a re-login on the next pass.
                async with self._lock:
                    self._token = None
                continue
            if resp.status in (401, 403):
                raise InsnrgAuthError("Insnrg rejected the session token")
            if resp.status != 200:
                raise InsnrgConnectionError(
                    f"Insnrg command {body.get('cmd')} returned HTTP {resp.status}"
                )
            return await resp.json(content_type=None)

        raise InsnrgConnectionError("Insnrg command failed after retry")

    async def async_get_devices(self) -> dict[str, dict[str, Any]]:
        """Fetch every device and normalise it into a dict keyed by device id."""
        raw = await self._async_cmd({"cmd": "getall"})
        if not isinstance(raw, list):
            raise InsnrgConnectionError("Unexpected `getall` response from Insnrg")
        if not raw:
            raise InsnrgVoiceControlDisabled(
                "Insnrg returned no devices. Enable Voice Control in the Insnrg "
                "app under Connected Systems."
            )

        devices: dict[str, dict[str, Any]] = {}
        for item in raw:
            device_id = item.get("deviceId")
            if not device_id:
                continue
            props = {
                prop.get("namespace"): prop.get("value")
                for prop in item.get("properties") or []
            }
            types = item.get("type") or []
            devices[device_id] = {
                "device_id": device_id,
                "name": item.get("name") or device_id,
                "type": types[0] if types else "",
                "types": types,
                "options": item.get("options") or [],
                "power": props.get(NS_POWER),
                "toggle": props.get(NS_TOGGLE),
                "mode": props.get(NS_MODE),
                "thermostat": props.get(NS_THERMOSTAT) or {},
                "temperature": props.get(NS_TEMPERATURE) or {},
            }
        return devices

    async def async_set_switch(self, device_id: str, mode: str) -> None:
        """Set a switch to ON, OFF or TIMER."""
        cmd_type = _SWITCH_COMMANDS.get(mode.upper())
        if cmd_type is None:
            raise ValueError(f"Unsupported switch mode: {mode}")
        await self._async_cmd(
            {"cmd": "setDeviceStatus", "cmdType": cmd_type, "deviceId": device_id}
        )

    async def async_set_light_mode(self, device_id: str, mode: str) -> None:
        """Set a light colour/effect mode."""
        await self._async_cmd(
            {"cmd": "setLightMode", "lightValue": mode, "deviceId": device_id}
        )

    async def async_set_pump_value(self, device_id: str, value: str) -> None:
        """Set pump speed or chlorinator output level."""
        await self._async_cmd(
            {"cmd": "setPumpValue", "pumpValue": value, "deviceId": device_id}
        )

    async def async_set_temperature(self, device_id: str, value: float) -> None:
        """Set a thermostat target temperature."""
        await self._async_cmd(
            {"cmd": "setTemperature", "tempValue": value, "deviceId": device_id}
        )

    async def async_set_chemistry(self, device_id: str, value: float) -> None:
        """Set a pH or ORP setpoint."""
        await self._async_cmd(
            {"cmd": "setChemistry", "chemValue": value, "deviceId": device_id}
        )
