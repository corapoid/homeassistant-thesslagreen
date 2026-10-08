[Wersja polska](README.md)

# Thessla Green for Home Assistant

A local Home Assistant integration for Thessla Green heat-recovery units and
the Particle+ purifier. Read measurements and alarms, control operating settings,
and edit AirPack4 schedules through a Modbus TCP → RTU gateway.

The most comprehensive profile targets **AirPack4 300h with controller firmware
4.89 and TG-02 firmware 0.30**. Home Assistant displays the configured model,
serial number and firmware versions read from the device.

## Requirements

- **Home Assistant 2025.10.0 or newer**.
- A gateway supporting **Modbus TCP**.
- The gateway host/IP, TCP port and device address, labelled **slave ID** in the form.
- Correct RTU settings. Manufacturer defaults are **9600 bps, 8N1**.

The form defaults to TCP port **8899**; set it to the port used by your gateway.
Raw RTU frames transported over TCP are not supported.

## Device profiles

| Configuration choice | Default slave ID | Purpose |
| --- | --- | --- |
| **AirPack4 300h** | 10 | Extended user functions for controller 4.89 / TG-02 0.30 |
| **Particle+** | 30 | Particle+500 with its own Modbus address |
| **Rekuperator — profil ogólny** | 10 | Original integration register map retained for existing entries |

Select the profile matching your device. Optional equipment such as GWC,
duct heaters and AFC depends on the installation.

## Installation

### HACS

1. Add `https://github.com/corapoid/homeassistant-thesslagreen` as a HACS custom repository
   in the **Integration** category.
2. Install **Thessla Green**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Thessla Green**, select a profile and enter the connection details.

You can also [open the Thessla Green configuration form directly](https://my.home-assistant.io/redirect/config_flow_start/?domain=thessla_green).
If it is missing from the list after restarting HA, hard-refresh the browser
(`Ctrl+Shift+R` or `Cmd+Shift+R`). In the mobile app, reopen the app and clear
the frontend cache if necessary. The integration is named **Thessla Green**,
not the repository name.

### Manual installation

1. Download or clone the repository:

   ```bash
   git clone --branch v0.4.0 https://github.com/corapoid/homeassistant-thesslagreen.git
   ```

2. Copy **only** `custom_components/thessla_green` from the repository into your
   HA configuration directory. The resulting layout should be:

   ```text
   <HA configuration directory>/
   └── custom_components/
       └── thessla_green/
           ├── __init__.py
           ├── manifest.json
           └── ...
   ```

3. Restart HA and add the integration as described above.

### Upgrading an existing installation

Update the integration and restart HA. For **AirPack4 300h**, select
**Model rekuperatora / Recuperator model → AirPack4 300h** in the existing entry's
options. Saving options automatically reloads the integration.

Add Particle+ as a **separate integration entry** with its own slave ID.

### Moving from the previous repository

Development now takes place in the independent **homeassistant-thesslagreen**
repository. Replace the previous HACS repository URL with the URL above and
install the current release. HA still uses the `thessla_green` domain and the
existing entity identifiers, so retain the configured integration entry.

## AirPack4 300h

### Device information and measurements

The device page and entities provide:

- Model, serial number, controller/TG-02 firmware and optional Expansion firmware.
- Outside, supply, extract, post-FPX, duct, GWC and unit-ambient temperatures.
- Airflow, ventilation intensity and Constant Flow status.
- FPX, ERV, bypass, KOMFORT and GWC states.
- O1 work confirmation, fan power and input/output states.
- Filter wear, replacement dates, active alarms and descriptions.
- Control-voltage diagnostics and time between Modbus updates.

Firmware versions are **read from the device**; the model comes from the selected
profile. Bypass automation permission is separate from actuator state and actual
bypass-function activity.

### Controls

| Function | Settings |
| --- | --- |
| Operation | Power, automatic/manual/temporary modes, summer/winter season |
| Ventilation | Manual/temporary intensity **10–100%**, AirS speed settings |
| KOMFORT and ERV | EKO/KOMFORT, ERV mode, target temperatures **10–45°C in 0.5°C steps** |
| Bypass | Permission, operating method, temperature thresholds, airflow balance and intensity |
| GWC | Permission, temperature thresholds, daily/temperature-based regeneration, duration and clocks |
| Special functions | Manual airing, fireplace, open windows, empty house, and their/hood parameters |
| Panel and name | Air++ language and the controller's stored device name |

Temporary settings write coupled values in one Modbus operation. Manual intensity
is a **manual-mode** setting. Sensors report functions activated by inputs or schedules.

### Schedules

Each weekday has **four periods**, separately for summer and winter. Set the
start time, intensity, temperature and enabled state. Scheduled and manual airing
have separate controls.

**Schedule entities are disabled by default.** Enable the required entities in
the device's entity settings. Detailed input diagnostics and some alarms are
exposed in the same way.

- Clocks have one-minute resolution.
- Setting a time enables the period; disabling writes the protocol sentinel.
- Enabling restores the remembered clock. After an entry reload, a disabled
  period uses its default clock.
- Editing intensity preserves the temperature packed into the same register,
  and vice versa.
- Schedules are read **every five minutes** and refreshed after HA writes.
  Panel changes may take that long to appear.

### Filters

Select the installed **filter-monitoring system** in integration options:

| Setting | Replacement-confirmation buttons |
| --- | --- |
| Unspecified | Unavailable |
| No AFC | Supply and extract filters |
| Supply AFC | Extract filter only |
| Extract AFC | Supply filter only |
| AFC on both filters | Unavailable — AFC monitors both filters |

Filter-check procedures and manufacturer-documented user alarm resets are also
available. Some buttons and detailed alarm entities must be enabled in entity settings.

## Particle+500

Select **Particle+** and enter the gateway address and purifier slave ID,
default **30**. It can share a gateway with the heat-recovery unit but requires
its own integration entry.

Supported features:

- Dust concentration from **PmSensor OUT / IN**.
- PM10/PM2.5 selection, manual/automatic operation and regulation mode.
- Power and manual intensity **10–100%**.
- Absolute target **0–200 µg/m³** and reference concentrations **10–300 µg/m³**.
- Filter pressure drops, wear, blocked filtration and alarms.
- From firmware **3.4.0**, missing work permission and missing-filter alarms.
- The `slave_screen` message, its raw code and filter-procedure state.
- Individual alarm codes, including **S116**, and an active-alarm summary.
- Measured controller firmware, serial number and read-only RTU-port settings.
- The panel's relative target, clock/alarm-record words and raw controller-name
  and firmware-compilation registers.

Sensors report the **selected particle type**, identified by `particle_type`.
Default device measurement intervals are **10 seconds** in automatic mode and
**30 minutes** in manual/off mode. Integration polling does not accelerate them.

Set the relative percentage target on the Particle+ panel. Automatic mode may
be unavailable if PmSensor OUT fails.

### Particle+ filter check and messages

**Particle+ Uruchom kontrolę filtrów** writes **3** to **42 / 0x002A**, without
a service code. It is unavailable while a check/calibration is running. Separate
entities configure the automatic check's weekday and time; Particle+ packs hour
and minute into two byte fields in register 44.

Observe **Particle+ Komunikat kontroli filtrów** and **Particle+ Kod komunikatu
filtrów**, reading **4398 / 0x112E**:

| Code | Meaning |
| --- | --- |
| `0x31` | New HEPA filter detected |
| `0x39` | Higher-than-original HEPA resistance; YES/NO decision required |
| `0x43` | Filter check running |
| `0x47` | Flow error during filter check |
| `0x48` | Filter-check procedure completed |
| `0x4A` | Cannot start the check; inspect alarms |

All manufacturer-documented message codes are decoded. Unknown codes retain
their raw value. A completion message **does not imply that S116 has cleared**;
the individual S116 alarm entity reports that bit independently.

Reads never acknowledge messages. The explicit acknowledgement button writes
`0` to `4398` and the next queued message is read again. Higher-resistance
questions require the separate **TAK / NIE** buttons, writing the decision to
**4400 / 0x1130**. Critical missing/invalid-filter messages cannot be acknowledged
with the acknowledgement button.

User reset buttons apply only to S2 and S255; there is no forced S116 reset.
Detailed alarm records and UART settings are disabled by default in HA.
Packed alarm dates, clock words and compilation fields are exposed as raw
diagnostics rather than guessing undocumented date encodings. Alarm records
refresh every five minutes and after HA commands; current alarms/messages
refresh on every poll.

## Efficiency, recovery power and COP

Recuperator profiles provide calculated temperature efficiency and recovery
power. For **COP**, select an **instantaneous-power sensor in W or kW** in options;
do not use an energy sensor reporting Wh/kWh.

The power sensor is optional and can be changed or cleared in options.
Efficiency requires valid temperatures and a sufficient temperature difference.
Recovery power and COP use positive CF airflow; COP additionally requires
positive power.
These values are calculated from readings, not direct performance measurements.

## Communication and troubleshooting

The standard polling interval is **30 seconds**, configured during setup.
Modbus commands are serialized, and a single request covers at most 16 registers.

| Symptom | Check |
| --- | --- |
| Setup fails | Host, port, slave ID, RTU settings and gateway availability; HA automatically retries setup |
| Integration missing after installation | Full HA restart, frontend refresh, direct configuration form and `/config/custom_components/thessla_green/manifest.json` |
| Entities are unavailable | Connection, integration logs, sensor/equipment availability |
| Missing schedules or detailed alarms | Enable the required entities from the device page |
| Filter replacement cannot be confirmed | Configure the installed AFC system; buttons apply to non-AFC filters |
| COP unavailable | Power sensor/units, valid temperatures, active CF and positive power/airflow |
| Panel schedule changes are delayed | Wait for the schedule poll — up to five minutes |

The AirPack4 model sensor exposes **`unsupported_registers`**, listing addresses
skipped after an explicit Modbus **Illegal Data Address** response. Reload after
hardware/firmware changes to retry detection. Timeouts and other device failures
are not treated as missing equipment.

Temperature `0x8000` and inactive-CF `0xFFFF` sentinels are not published as
negative measurements or used in calculations.

## Development and tests

Use a Python version supported by the Home Assistant release you install:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m pytest -q
```

Reproduce the minimum CI environment with **Python 3.13**:

```bash
python3.13 -m venv .venv-min
.venv-min/bin/python -m pip install -r requirements-test.txt \
  -c tests/constraints-ha-2025.10.txt \
  "homeassistant==2025.10.0" "pymodbus==3.11.2"
.venv-min/bin/python -m pytest -q
```

Tests cover decoding, commands, schedules, communication errors, integration
lifecycle, the HA device registry, and local TCP gateways exercised by the real
pymodbus client. CI checks minimum and current dependency versions.

## Project status and references

Current release: **v0.4.0**. The release page provides the integration archive
and `SHA256SUMS`. Documentation and release files come from the same tag.

Changes awaiting publication are marked **Unreleased** in [CHANGELOG.md](CHANGELOG.md).
Physical-device verification is pending; profile coverage is based on manufacturer
documentation and automated tests.

- [Integration releases](https://github.com/corapoid/homeassistant-thesslagreen/releases)
- [Issue tracker](https://github.com/corapoid/homeassistant-thesslagreen/issues)
- [AirPack4 Modbus protocol](https://thesslagreen.com/wp-content/uploads/MODBUS_USER_AirPack_4_10.2022.01.pdf)
- [Particle+ Modbus protocol](https://thesslagreen.com/wp-content/uploads/MODBUS_USER_Particle_08.2021.01.pdf)

The AirPack4 profile covers user functions. Installer calibration, product-key
programming and Modbus-port configuration are outside its scope.

## License

The project is distributed under the [MIT license](LICENSE).

Project history and author contributions originate from
[aLAN-LDZ's ThesslaGreen_HA](https://github.com/aLAN-LDZ/ThesslaGreen_HA).
The independent repository preserves that history and its earlier tags.

### Publishing a release

The manifest version and a changelog section must match the `vX.Y.Z` tag.
Build and validate release artifacts locally with:

```bash
python scripts/build_release.py v0.4.0 --output-dir dist
```

Pushing a tag runs the **Release** workflow. Tests and HACS/hassfest validation
must pass before the workflow publishes the GitHub release, changelog notes,
integration archive and SHA256 checksum. A suffix such as `v0.4.0-beta.1`
marks a prerelease.
