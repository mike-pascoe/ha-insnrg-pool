"""Client for the Insnrg app's own API.

This is the Cognito-backed API behind insnrgapp.com. It needs no special
account flags, and carries maintenance telemetry -- cell life, electrode
volts/amps, probe hours -- that the third-party control API does not expose.
It is read-only here; all writes go through `api.InsnrgClient`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from aiohttp import ClientError, ClientSession

from homeassistant.core import HomeAssistant

from .api import InsnrgAuthError, InsnrgConnectionError

_LOGGER = logging.getLogger(__name__)

COGNITO_REGION = "us-east-2"
COGNITO_POOL_ID = "us-east-2_qrnmEYVSG"
COGNITO_CLIENT_ID = "50kmkes69ij352vpq3ec7dfki2"

SYSTEMS_URL = "https://69lfsbfsrb.execute-api.us-east-2.amazonaws.com/prod/all"
ACTION_URL = "https://imnwf40hng.execute-api.us-east-2.amazonaws.com/prod/actionApi"

_TOKEN_LEEWAY = 120


class InsnrgAppClient:
    """Read-only client for the Insnrg app API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._hass = hass
        self._session = session
        self._username = username
        self._password = password
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._expires_at = 0.0
        self.system_id: str | None = None

    def _authenticate_sync(self) -> dict[str, Any]:
        """Run SRP authentication. Blocking -- must go through the executor."""
        import boto3
        from pycognito import AWSSRP

        client = boto3.client("cognito-idp", region_name=COGNITO_REGION)
        srp = AWSSRP(
            username=self._username,
            password=self._password,
            pool_id=COGNITO_POOL_ID,
            client_id=COGNITO_CLIENT_ID,
            client=client,
        )
        return srp.authenticate_user()

    async def async_login(self) -> None:
        """Authenticate and cache the id token."""
        try:
            result = await self._hass.async_add_executor_job(self._authenticate_sync)
        except Exception as err:  # noqa: BLE001 - botocore raises many shapes
            name = type(err).__name__
            if "NotAuthorized" in name or "UserNotFound" in name:
                raise InsnrgAuthError("Insnrg rejected the username or password") from err
            raise InsnrgConnectionError(f"Insnrg app login failed: {err}") from err

        auth = result.get("AuthenticationResult") or {}
        token = auth.get("IdToken")
        if not token:
            raise InsnrgAuthError("Insnrg app login returned no token")
        self._token = token
        self._expires_at = time.time() + float(auth.get("ExpiresIn") or 3600)

    async def _async_token(self) -> str:
        async with self._lock:
            if self._token is None or time.time() >= self._expires_at - _TOKEN_LEEWAY:
                await self.async_login()
            assert self._token is not None
            return self._token

    async def _async_post(self, url: str, body: dict[str, Any] | None) -> Any:
        token = await self._async_token()
        try:
            resp = await self._session.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
        except (ClientError, asyncio.TimeoutError) as err:
            raise InsnrgConnectionError(f"Could not reach Insnrg app API: {err}") from err

        if resp.status in (401, 403):
            async with self._lock:
                self._token = None
            raise InsnrgAuthError("Insnrg app API rejected the session token")
        if resp.status != 200:
            raise InsnrgConnectionError(f"Insnrg app API returned HTTP {resp.status}")
        return await resp.json(content_type=None)

    async def async_get_system_id(self) -> str | None:
        """Find the first active system on the account."""
        data = await self._async_post(SYSTEMS_URL, None)
        for item in (data or {}).get("data") or []:
            if item.get("isActive"):
                self.system_id = item.get("systemId")
                return self.system_id
        return None

    async def async_get_dashboard(self) -> dict[str, Any]:
        """Fetch the dashboard screen, which carries maintenance telemetry."""
        if self.system_id is None:
            await self.async_get_system_id()
        if self.system_id is None:
            raise InsnrgConnectionError("No active Insnrg system on this account")

        data = await self._async_post(
            ACTION_URL,
            {
                "systemId": self.system_id,
                "params": "DashboardScreen",
                "action": "view",
            },
        )
        dashboard = (data or {}).get("dashboard") or {}
        system = (data or {}).get("system") or {}

        result: dict[str, Any] = {}

        # Consumable / service-life counters, keyed by the API's own ids.
        for item in dashboard.get("pumpAcids") or []:
            if item.get("isEnable") and not item.get("isHiden") and item.get("id"):
                result[item["id"]] = {
                    "value": item.get("value"),
                    "max": item.get("max"),
                    "name": item.get("title"),
                }

        # Electrode readings.
        for item in dashboard.get("chlorinators") or []:
            if item.get("id"):
                result[item["id"]] = {"value": item.get("value"), "name": item.get("text")}

        for item in dashboard.get("reversals") or []:
            if item.get("id"):
                result[item["id"]] = {"value": item.get("value"), "name": item.get("text")}

        for item in dashboard.get("filterHours") or []:
            if item.get("isEnable") and item.get("id"):
                result[item["id"]] = {
                    "value": item.get("value"),
                    "max": item.get("max"),
                    "name": item.get("title"),
                }

        gas = dashboard.get("gasHeater") or {}
        if "value" in gas:
            result["gasHeaterHours"] = {
                "value": gas.get("value"),
                "max": gas.get("max"),
                "name": "Gas heater hours",
            }

        wifi = dashboard.get("wifiSignalStrength")
        if isinstance(wifi, (int, float)):
            result["wifiSignalStrength"] = {"value": _wifi_dbm(wifi), "name": "WiFi signal"}

        live = system.get("liveData")
        if isinstance(live, str) and live:
            try:
                result["liveData"] = json.loads(live)
            except json.JSONDecodeError:
                _LOGGER.debug("Could not parse liveData")

        return result


def _wifi_dbm(raw: float) -> float:
    """Convert the API's unsigned 16-bit RSSI into dBm."""
    value = int(raw)
    if value > 32767:
        value -= 65536
    return float(value)
