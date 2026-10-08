# Changelog

All notable changes to this integration are documented here.
Entries under **Unreleased** describe development changes awaiting a release.

## [Unreleased]

## [0.3.1] - 2026-10-08

### Changed

- Move maintained development and releases to the independent, non-fork
  repository `corapoid/homeassistant-thesslagreen`.
- Update HACS installation, documentation, issue-tracker and release URLs.
- Preserve commit history, earlier tags and the original v0.3.0 release assets;
  keep the `thessla_green` integration domain and entity identifiers.
- Document migration from the previous HACS repository and credit the original
  project contributors.

## [0.3.0] - 2026-10-08

### Added

- MIT license, included in release archives.
- Device-profile selection for the existing generic recuperator integration,
  **Particle+500**, and **AirPack4 300h**.
- Particle+ support using the manufacturer's dedicated holding-register map:
  OUT/IN dust concentration, PM10/PM2.5 selection, filter pressure drops and wear,
  power, operating/regulation modes, filtration intensity and dust targets.
- Particle+ extended alarms for firmware **3.4.0 and newer**, including missing
  work permission and missing prefilter/HEPA filter.
- AirPack4 300h user-function profile targeting controller **4.89** and
  **TG-02 0.30**: automatic/manual/temporary operation, EKO/KOMFORT, ERV,
  bypass, GWC/regeneration, special-function parameters and AirS speed settings.
- AirPack4 summer/winter schedules with four periods per day, editable BCD
  start times, intensity, temperature and period enable controls; separate
  scheduled/manual airing and GWC regeneration clocks.
- AirPack4 filter wear/replacement dates, filter-check procedures,
  replacement-confirmation buttons appropriate to the installed AFC system,
  and documented user-resettable alarm buttons.
- AirPack4 discrete inputs, relay outputs, analog control-voltage diagnostics,
  active alarm descriptions, Air++ language selection and controller-name editing.
- Device information and diagnostic sensors for the AirPack4 model, serial
  number, measured controller/TG-02 firmware and optional Expansion firmware.
- Polish and English configuration/options translations.
- Standalone English documentation in `README.en.md`, linked from the top
  of the Polish README and included in release archives.
- Regression tests covering real HA entries, coordinator notifications,
  device-registry metadata, state-change events, and stateful local Modbus TCP
  gateways using the real pymodbus client.
- CI testing minimum supported HA/pymodbus versions and current releases.
- Tag-driven releases gated on tests, HACS and hassfest, with manifest/tag
  consistency checks, changelog-derived notes and downloadable SHA256 checksums.
- Weekly Dependabot updates for GitHub Actions.

### Changed

- Rebuild the Polish README as an installation, configuration and diagnostics
  guide; remove badges and the embedded English section.
- Update checkout/setup-python to v7 and action-gh-release to v3; pin the
  JavaScript actions to reviewed release commit hashes.
- Existing recuperator entries can select the AirPack4 profile through options;
  changing options automatically reloads the integration.
- Recuperator entities use coordinator notifications instead of redundant HA
  polling, retaining existing entity/device identifiers.
- Modbus operations are serialized; AirPack4 temporary settings use atomic
  FC16 writes, and packed schedule settings use locked read-modify-write.
- AirPack4 optional registers are skipped only after an explicit **Illegal Data
  Address** response. Supported neighbours remain readable; transport/device
  failures still make entities unavailable.
- Schedule registers are cached for five minutes and refreshed after HA writes.
- Modbus requests respect the manufacturer's 16-register limit. Response
  lengths are checked, coil padding is discarded, and update intervals use a
  monotonic clock.
- Manual recuperator intensity is restricted to the documented **10–100%**.
- The external COP power sensor is optional and can be cleared from options;
  only supported instantaneous-power units are accepted.
- Test requirements match the HACS minimum of **Home Assistant 2025.10.0**;
  pymodbus is constrained to `>=3.11.2,<4.0`.
- Release archives validate successfully before upload, exclude generated
  caches, include documentation/changelog, and fail on packaging/upload errors.
- Publish fork releases from `corapoid/ThesslaGreen_HA` and point documentation
  and issue-tracker links to the maintained fork.

### Fixed

- Preserve `ConfigEntryNotReady` so Home Assistant retries unavailable devices
  during startup; close clients after failed setup.
- Retain the controller and stored data when platform unloading fails.
- Report write/validation failures to HA instead of silently logging them.
- Correct inverted ERV state, active FPX2 interpretation, bypass-permission
  labelling, fan-power/work-confirmation distinction and ambient-temperature name.
- Treat temperature `0x8000` and CF airflow `0xFFFF` as unavailable measurements
  rather than negative values; exclude them from efficiency/power/COP calculations.
- Reject non-finite power values and unsupported units in COP calculations.
- Remove duplicate/undocumented reads from the AirPack4 register map and keep
  the legacy numeric operating-mode sensor identity/value format.
- Correct manual installation instructions to copy the integration directory
  rather than nest the entire repository under `custom_components`.

### Validation

- Automated tests pass on HA **2025.10.0 / Python 3.13 / pymodbus 3.11.2** and
  HA **2026.10.0 / Python 3.14 / pymodbus 3.15.0**.
- Physical-device verification is pending; tests exercise simulated gateways
  and real Home Assistant registry/coordinator APIs.

[Unreleased]: https://github.com/corapoid/homeassistant-thesslagreen/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/corapoid/homeassistant-thesslagreen/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/corapoid/homeassistant-thesslagreen/compare/5bae9f4...v0.3.0
