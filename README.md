# Insnrg Pool for Home Assistant

Control and monitor an [Insnrg inTouch](https://www.insnrg.com/) pool system from Home
Assistant — pump, heater, spa, lights, chlorinator, timers and water chemistry — as
native `switch`, `light`, `climate`, `number`, `select` and `sensor` entities.

Unofficial. Not affiliated with or endorsed by Insnrg.

## Requirements

- An account on [insnrgapp.com](https://www.insnrgapp.com)
- **Voice Control must be enabled**: in the Insnrg app, open **Connected Systems** and
  turn on **Voice Control**. Until you do, the control API reports zero devices and
  setup will fail with *"Insnrg returned no devices"*.

## Installation

### HACS

1. HACS → three-dot menu → **Custom repositories**
2. Add this repository's URL, category **Integration**
3. Install **Insnrg Pool**, then restart Home Assistant
4. **Settings → Devices & Services → Add Integration → Insnrg Pool**

### Manual

Copy `custom_components/insnrg_pool` into your `config/custom_components/` directory
and restart Home Assistant.

## Entities

Everything lives under a single device named after your pool system.

| Entity | Type | Notes |
| --- | --- | --- |
| Filter Pump, Spa, Gas Heater, Jet Pump, Ozone, Blower | `switch` | One per appliance on your system |
| All Auto | `switch` | Master timer-schedule enable |
| Timer 1–4 Status / Chlorinator | `switch` | Enable a timer slot, and whether it runs the chlorinator |
| Lights | `light` | On/off, with the 11 colour programs exposed as **effects** |
| Water Thermostat, Spa thermostat | `climate` | Heat setpoint and measured water temperature |
| Pump Speed | `select` | `Default`, `1`–`4` |
| Chlorinator Level | `select` | `0%`–`100%` |
| *<appliance>* mode | `select` | `ON` / `OFF` / `TIMER` — see below |
| pH setpoint, ORP setpoint | `number` | Targets the chlorinator doses towards |
| pH, ORP, Water temperature | `sensor` | Live readings |
| Cell life, Gas heater hours | `sensor` | Service-life counters, with `service_life_hours` attribute |
| pH / ORP probe life, Acid squeeze tube life | `sensor` | Diagnostic |
| Cell voltage, Cell current, WiFi signal | `sensor` | Diagnostic (WiFi disabled by default) |

### On/off vs. timer mode

Appliances that can follow the timer schedule have a third state that a plain switch
cannot express. Those get an extra `select` entity alongside the switch:

- `ON` — forced on, ignoring timers
- `OFF` — forced off
- `TIMER` — follows the timer schedule

The `switch` still reports whether the appliance is drawing power right now, and
carries a `timer_mode` attribute. Use the `select` when you want to hand control
back to the schedule rather than pin the appliance on or off.

## Configuration

The polling interval is configurable under the integration's **Configure** button
(default 5 minutes). Maintenance counters poll every 30 minutes regardless — they
move in hours, not minutes.

This is a cloud-polled integration: state changes made at the pool or in the Insnrg
app appear in Home Assistant at the next poll, not instantly. After Home Assistant
issues a command it waits briefly, then re-polls, so the entity settles on the real
state rather than an optimistic guess.

## How it works

The integration talks to two Insnrg APIs:

- **Control API** (`4rsb9rvte4.execute-api.us-east-2.amazonaws.com`) — the endpoint
  behind Voice Control. Plain username/password login; supports reads and writes.
  This drives every controllable entity.
- **App API** (`imnwf40hng.execute-api.us-east-2.amazonaws.com`) — the Cognito-backed
  API behind insnrgapp.com. Read-only here, and the only source of the maintenance
  telemetry (cell life, electrode volts/amps, probe hours). Requires no account flags.

Session tokens from both are cached and reused until they expire, rather than
re-authenticating on every call.

If the app API is unreachable the integration still sets up — you lose the diagnostic
sensors, not the controls.

## Known quirks

- The API reports probe- and tube-life counters as negative numbers on some systems.
  The values are passed through as-is.
- pH setpoint bounds are fixed at 7.0–8.0 rather than read from the API, whose
  `valueMax` for pH tracks the current reading instead of a real limit.
- The thermostats expose a setpoint but no on/off — heating is gated by the Gas Heater
  switch — so they report a single `heat` mode.

## Credits

API shape originally mapped by [Mattat01/insnrg_chlorinator](https://github.com/Mattat01/insnrg_chlorinator)
and [jaringuyen/InsnrgHomeAssistance](https://github.com/jaringuyen/InsnrgHomeAssistance).
