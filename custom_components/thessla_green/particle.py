"""Particle+ entities using MODBUS_USER_Particle_08.2021.01 registers."""

from datetime import time

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_DEVICE_TYPE, DEVICE_PARTICLE, DOMAIN
from .const import PARTICLE_FIRMWARE_REGISTER, PARTICLE_EXTENDED_ALARMS_VERSION
from .entity import ModbusEntity, integer_setting
from .particle_registers import (
    BASE_ALARMS, EXTENDED_ALARMS, FILTER_MESSAGES, FILTER_QUESTIONS,
    FILTER_CRITICAL_MESSAGES, FILTER_BUSY_MESSAGES,
    FILTER_PROCEDURE_REGISTER, FILTER_MESSAGE_REGISTER, FILTER_ANSWER_REGISTER, START_FILTER_CHECK,
)


def is_particle(entry):
    """Entries created before device profiles remain recuperators."""
    return entry.data.get(CONF_DEVICE_TYPE) == DEVICE_PARTICLE


def particle_information(registers):
    firmware = None
    raw = registers.get(PARTICLE_FIRMWARE_REGISTER)
    if raw not in (None, 0, 0xFFFF):
        firmware = f"{raw >> 8}.{raw & 255}"
        patch = registers.get(8132)
        if raw >= PARTICLE_EXTENDED_ALARMS_VERSION and patch not in (None, 0xFFFF):
            firmware += f".{patch}"
    words = [registers.get(address) for address in range(8128, 8131)]
    serial = None
    if all(word is not None for word in words) and any(words) and words != [0xFFFF] * 3:
        serial = "".join(f"{word:04x}" for word in words)
    return firmware, serial


def particle_alarm_definitions(registers):
    modern = registers.get(PARTICLE_FIRMWARE_REGISTER, 0) >= PARTICLE_EXTENDED_ALARMS_VERSION
    definitions = []
    for index, (code, mask, name) in enumerate(BASE_ALARMS):
        actual_code = ("E8" if modern else "S8") if code == "PM_OUT" else code
        key = "pm_out" if code == "PM_OUT" else code.lower()
        definitions.append((key, actual_code, name, 96, mask, 1536 + index * 4))
    if modern:
        for index, (code, mask, name) in enumerate(EXTENDED_ALARMS):
            definitions.append((code.lower(), code, name, 98, mask, 1600 + index * 4))
    return definitions


class ParticleEntity(ModbusEntity):
    """Share identity, register access and write error handling."""

    def __init__(self, coordinator, entry, key, name, address):
        super().__init__(coordinator)
        self._key = key
        self._address = address
        self._attr_name = f"Particle+ {name}"
        self._attr_unique_id = f"thessla_particle_{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"particle_{entry.entry_id}")},
            "name": "Thessla Green Particle+",
            "manufacturer": "Thessla Green",
            "model": "Particle+500",
        }

    @property
    def available(self):
        return super().available and self.raw_value is not None

    @property
    def device_info(self):
        info = dict(self._attr_device_info)
        firmware, serial = particle_information(self.coordinator.safe_data.holding)
        if firmware:
            info["sw_version"] = firmware
        if serial:
            info["serial_number"] = serial
        return info

    @property
    def raw_value(self):
        return self.coordinator.safe_data.holding.get(self._address)

    async def _write(self, value):
        await self._async_write_register(self._address, value)


class ParticleSensor(ParticleEntity, SensorEntity):
    """Read numeric measurements, including signed differential pressures."""

    _attr_state_class = "measurement"

    def __init__(self, coordinator, entry, key, name, address, unit, signed=False, device_class=None):
        super().__init__(coordinator, entry, key, name, address)
        self._signed = signed
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if address in (4114, 4115):
            self._attr_icon = "mdi:air-filter"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        value = self.raw_value
        if value is not None and self._signed and value > 0x7FFF:
            return value - 0x10000
        return value

    @property
    def extra_state_attributes(self):
        if self._address in (50, 51):
            return {"particle_type": {0: "PM10", 1: "PM2.5"}.get(
                self.coordinator.safe_data.holding.get(48)
            )}
        return None


class ParticleBinarySensor(ParticleEntity, BinarySensorEntity):
    """Read a status flag or an alarm bit mask."""

    _attr_device_class = "problem"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, key, name, address, mask=1):
        super().__init__(coordinator, entry, key, name, address)
        self._mask = mask

    @property
    def is_on(self):
        value = self.raw_value
        return None if value is None else bool(value & self._mask)


class ParticleAlarmSensor(ParticleBinarySensor):
    """Combine the original and firmware-dependent alarm tables."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "alarm", "Alarm", 96, 0xFFFF)

    @property
    def available(self):
        firmware = self.coordinator.safe_data.holding.get(PARTICLE_FIRMWARE_REGISTER, 0)
        return super().available and (
            firmware < PARTICLE_EXTENDED_ALARMS_VERSION
            or self.coordinator.safe_data.holding.get(98) is not None
        )

    @property
    def is_on(self):
        if self.raw_value is None:
            return None
        extended = self.coordinator.safe_data.holding.get(98, 0)
        return bool(self.raw_value or extended)


class ParticlePowerSwitch(ParticleEntity, SwitchEntity):
    """Control the documented power register."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "power", "Zasilanie", 16)

    @property
    def is_on(self):
        return None if self.raw_value is None else self.raw_value == 1

    async def async_turn_on(self, **kwargs):
        await self._write(1)

    async def async_turn_off(self, **kwargs):
        await self._write(0)


class ParticleSelect(ParticleEntity, SelectEntity):
    """Control a register with a fixed set of documented values."""

    def __init__(self, coordinator, entry, key, name, address, options):
        super().__init__(coordinator, entry, key, name, address)
        self._options = options
        self._attr_options = list(options)

    @property
    def current_option(self):
        return next((name for name, value in self._options.items() if value == self.raw_value), None)

    async def async_select_option(self, option):
        if option not in self._options:
            raise HomeAssistantError(f"Unknown Particle+ option: {option}")
        await self._write(self._options[option])


class ParticleNumber(ParticleEntity, NumberEntity):
    """Control bounded numeric settings without rounding invalid commands."""

    _attr_native_step = 1

    def __init__(self, coordinator, entry, key, name, address, unit, minimum, maximum):
        super().__init__(coordinator, entry, key, name, address)
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum

    @property
    def native_value(self):
        return self.raw_value

    async def async_set_native_value(self, value):
        await self._write(integer_setting(value, self._attr_native_min_value, self._attr_native_max_value))


class ParticleDiagnosticSensor(ParticleSensor):
    _attr_state_class = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, key, name, address, decoder=None, unit=None):
        super().__init__(coordinator, entry, key, name, address, unit)
        self._decoder = decoder

    @property
    def native_value(self):
        raw = self.raw_value
        return None if raw is None else self._decoder(raw) if self._decoder else raw

    @property
    def extra_state_attributes(self):
        raw = self.raw_value
        return {"register": self._address, "code": raw,
                "code_hex": f"0x{raw:02X}" if raw is not None else None}


class ParticleInformationSensor(ParticleDiagnosticSensor):
    def __init__(self, coordinator, entry, key, name, address, index):
        super().__init__(coordinator, entry, key, name, address)
        self._index = index

    @property
    def native_value(self):
        return particle_information(self.coordinator.safe_data.holding)[self._index]

    @property
    def available(self):
        return super().available and self.native_value is not None


class ParticleMessageSensor(ParticleDiagnosticSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "filter_message", "Komunikat kontroli filtrów", FILTER_MESSAGE_REGISTER,
                         decoder=lambda code: FILTER_MESSAGES.get(code, f"Nieznany komunikat (0x{code:02X})"))

    @property
    def extra_state_attributes(self):
        return {**super().extra_state_attributes, "answer_required": self.raw_value in FILTER_QUESTIONS}


class ParticleActiveAlarmsSensor(ParticleDiagnosticSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "active_alarms", "Aktywne alarmy", 96)

    @property
    def active_codes(self):
        registers = self.coordinator.safe_data.holding
        return {code: name for key, code, name, address, mask, history in particle_alarm_definitions(registers)
                if registers.get(address, 0) & mask}

    @property
    def native_value(self):
        return ", ".join(self.active_codes) if self.active_codes else "Brak"

    @property
    def available(self):
        registers = self.coordinator.safe_data.holding
        modern = registers.get(PARTICLE_FIRMWARE_REGISTER, 0) >= PARTICLE_EXTENDED_ALARMS_VERSION
        return super().available and (not modern or 98 in registers)

    @property
    def extra_state_attributes(self):
        registers = self.coordinator.safe_data.holding
        return {"alarm_descriptions": self.active_codes, "primary_flags": registers.get(96),
                "extended_flags": registers.get(98)}


class ParticleRecordedAlarmSensor(ParticleDiagnosticSensor):
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry, key, code, address):
        super().__init__(coordinator, entry, f"history_{key}", f"Rejestracja alarmu {code}", address + 3)
        self._start = address

    @property
    def native_value(self):
        return {0: "Brak flagi", 1: "Flaga załączenia"}.get(self.raw_value)

    @property
    def available(self):
        registers = self.coordinator.safe_data.holding
        return super().available and all(address in registers for address in range(self._start, self._start + 4))

    @property
    def extra_state_attributes(self):
        registers = self.coordinator.safe_data.holding
        # Preserve packed date words without guessing their calendar encoding.
        return {"register": self._start,
                "year_month_raw": registers.get(self._start),
                "day_hour_raw": registers.get(self._start + 1),
                "minute_second_raw": registers.get(self._start + 2),
                "alarm_flag": self.raw_value,
                "packed_words_hex": [f"0x{registers[address]:04X}" if address in registers else None
                                     for address in range(self._start, self._start + 4)]}


class ParticleClockRegistersSensor(ParticleDiagnosticSensor):
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "clock_registers", "Zegar sterownika — rejestry", 0)

    @property
    def native_value(self):
        registers = self.coordinator.safe_data.holding
        if not all(address in registers for address in range(4)):
            return None
        return " / ".join(f"0x{registers[address]:04X}" for address in range(4))

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self):
        return {"format": ["RRMM", "DDTT", "GGmm", "sscc"],
                "registers": [self.coordinator.safe_data.holding.get(address) for address in range(4)]}


class ParticleStatusFlag(ParticleBinarySensor):
    _attr_device_class = None

    def __init__(self, coordinator, entry, key, name, address, values):
        super().__init__(coordinator, entry, key, name, address)
        self._values = values

    @property
    def is_on(self):
        return None if self.raw_value is None else self.raw_value in self._values


class ParticleCommandButton(ParticleEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, key, name, address, value, condition=None):
        super().__init__(coordinator, entry, key, name, address)
        self._value = value
        self._condition = condition

    @property
    def available(self):
        return super().available and (self._condition is None or self._condition(self.coordinator.safe_data.holding))

    async def async_press(self):
        if not self.available:
            raise HomeAssistantError("Polecenie niedostępne w aktualnym stanie Particle+")
        await self._write(self._value)


class ParticleFilterCheckTime(ParticleEntity, TimeEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "filter_check_time", "Godzina automatycznej kontroli filtrów", 44)

    @property
    def native_value(self):
        if self.raw_value is None:
            return None
        try:
            return time(self.raw_value >> 8, self.raw_value & 255)
        except ValueError:
            return None

    async def async_set_value(self, value):
        if not isinstance(value, time) or value.second or value.microsecond or value.tzinfo is not None:
            raise HomeAssistantError("Wymagana lokalna godzina z dokładnością do minuty")
        await self._write((value.hour << 8) | value.minute)


def particle_entities(platform, coordinator, entry):
    """Build only entities supported by the Particle+ register map."""
    registers = coordinator.safe_data.holding
    modern = registers.get(PARTICLE_FIRMWARE_REGISTER, 0) >= PARTICLE_EXTENDED_ALARMS_VERSION
    alarms = particle_alarm_definitions(registers)
    if platform == "sensor":
        entities = [ParticleSensor(coordinator, entry, *definition) for definition in (
            ("dust_out", "Stężenie pyłu OUT", 50, "µg/m³"),
            ("dust_in", "Stężenie pyłu IN", 51, "µg/m³"),
            ("pressure_prefilter", "Spadek ciśnienia filtra wstępnego", 33, "Pa", True, "pressure"),
            ("pressure_hepa", "Spadek ciśnienia filtra HEPA", 36, "Pa", True, "pressure"),
            ("automatic_intensity", "Intensywność filtracji automatycznej", 64, "%"),
            ("target", "Obliczona nastawa stężenia pyłu", 56, "µg/m³"),
            ("prefilter_wear", "Zużycie filtra wstępnego", 4114, "%"),
            ("hepa_wear", "Zużycie filtra HEPA", 4115, "%"),
        )]
        entities.extend([
            ParticleMessageSensor(coordinator, entry),
            ParticleDiagnosticSensor(coordinator, entry, "filter_message_code", "Kod komunikatu filtrów", 4398),
            ParticleDiagnosticSensor(coordinator, entry, "filter_procedure", "Procedura filtrów", 42,
                                     decoder=lambda raw: {0: "Normalna filtracja", 3: "Kontrola filtrów"}.get(raw, f"Nieopisany tryb ({raw})")),
            ParticleDiagnosticSensor(coordinator, entry, "relative_target", "Nastawa względna stężenia pyłu", 55, unit="%"),
            ParticleDiagnosticSensor(coordinator, entry, "alarm_flags", "Rejestr alarmów — część 1", 96),
            ParticleDiagnosticSensor(coordinator, entry, "language_code", "Język panelu — kod", 4399),
            ParticleDiagnosticSensor(coordinator, entry, "device_name_register", "Nazwa urządzenia — rejestr", 8144),
            ParticleClockRegistersSensor(coordinator, entry),
            ParticleActiveAlarmsSensor(coordinator, entry),
            ParticleInformationSensor(coordinator, entry, "firmware", "Wersja sterownika", 8131, 0),
            ParticleInformationSensor(coordinator, entry, "serial", "Numer seryjny", 8128, 1),
        ])
        for port, first, name in (("airpp", 112, "Air++"), ("air_b", 117, "Air-B")):
            baud = {0: "9600 bps", 1: "19200 bps", 2: "38400 bps", 3: "57600 bps"}
            parity = {0: "Brak", 1: "Parzysta", 2: "Nieparzysta"}
            stop = {0: "1 bit", 1: "2 bity"}
            for offset, field, label, values in (
                (0, "id", "Slave ID", None), (1, "baud", "Prędkość RTU", baud),
                (2, "parity", "Parzystość", parity), (3, "stop", "Bity stopu", stop),
                (4, "uart", "Rejestr reinicjalizacji UART", None),
            ):
                decoder = (lambda raw, options=values: options.get(raw, f"Nieznany kod ({raw})")) if values else None
                entity = ParticleDiagnosticSensor(coordinator, entry, f"{port}_{field}", f"{name} — {label}", first + offset, decoder)
                entity._attr_entity_registry_enabled_default = False
                entities.append(entity)
        if modern:
            entities.extend(ParticleDiagnosticSensor(coordinator, entry, key, name, address)
                            for key, name, address in (
                                ("alarm_flags_extended", "Rejestr alarmów — część 2", 98),
                                ("firmware_patch", "Wersja sterownika — patch", 8132),
                                ("compilation_date_raw", "Data kompilacji — rejestr", 8133),
                                ("compilation_time_raw", "Godzina kompilacji — rejestr", 8134),
                            ))
        entities.extend(ParticleRecordedAlarmSensor(coordinator, entry, key, code, history)
                        for key, code, name, address, mask, history in alarms)
        return entities
    if platform == "binary_sensor":
        entities = [ParticleBinarySensor(coordinator, entry, *definition) for definition in (
            ("blocked", "Filtracja wstrzymana", 41),
            ("fan_fault", "Awaria wentylatora", 96, 0x0001),
            ("out_sensor_fault", "Awaria PmSensor OUT", 96, 0x0002),
            ("in_sensor_fault", "Awaria PmSensor IN", 96, 0x0004),
            ("hepa_replace", "Wymiana filtra HEPA", 96, 0x01A0),
            ("prefilter_replace", "Wymiana filtra wstępnego", 96, 0x1A00),
        )]
        entities.insert(1, ParticleAlarmSensor(coordinator, entry))
        if modern:
            entities.extend(ParticleBinarySensor(coordinator, entry, *definition) for definition in (
                ("permission_missing", "Brak zezwolenia na pracę", 98, 0x0001),
                ("prefilter_missing", "Brak filtra wstępnego", 98, 0x0002),
                ("hepa_missing", "Brak filtra HEPA", 98, 0x0004),
            ))
            entities.extend([
                ParticleBinarySensor(coordinator, entry, "warnings", "Ostrzeżenia E", 8192),
                ParticleBinarySensor(coordinator, entry, "errors", "Błędy S", 8193),
                ParticleStatusFlag(coordinator, entry, "work_permission", "Zewnętrzne zezwolenie na pracę T2", 12352, (1,)),
            ])
        for key, code, name, address, mask, history in alarms:
            alarm = ParticleBinarySensor(coordinator, entry, f"alarm_{key}", f"{code} — {name}", address, mask)
            entities.append(alarm)
        running = ParticleStatusFlag(coordinator, entry, "filter_check_running", "Kontrola filtrów trwa", 42, (3,))
        running._attr_device_class = "running"
        calibration = ParticleStatusFlag(coordinator, entry, "filter_calibration_running", "Kalibracja filtrów trwa", 4398, (0x42,))
        calibration._attr_device_class = "running"
        entities.extend([
            running, calibration,
            ParticleStatusFlag(coordinator, entry, "filter_answer_required", "Wymagana decyzja o użyciu filtra", 4398, FILTER_QUESTIONS),
        ])
        return entities
    if platform == "switch":
        return [ParticlePowerSwitch(coordinator, entry)]
    if platform == "select":
        entities = [ParticleSelect(coordinator, entry, *definition) for definition in (
            ("mode", "Tryb pracy", 17, {"Manualny": 0, "Automatyczny": 1}),
            ("particle_type", "Rodzaj pyłu", 48, {"PM10": 0, "PM2.5": 1}),
            ("regulation", "Sposób regulacji", 53, {"Bezwzględny": 0, "Względny": 1}),
        )]
        day = ParticleSelect(coordinator, entry, "filter_check_day", "Dzień automatycznej kontroli filtrów", 43,
                             {name: index for index, name in enumerate(("Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"))})
        language = ParticleSelect(coordinator, entry, "language", "Język panelu Air++", 4399, {"Polski": 0, "English": 1})
        day._attr_entity_category = EntityCategory.CONFIG
        language._attr_entity_category = EntityCategory.CONFIG
        return entities + [day, language]
    if platform == "number":
        return [ParticleNumber(coordinator, entry, *definition) for definition in (
            ("manual_intensity", "Intensywność filtracji manualnej", 65, "%", 10, 100),
            ("absolute_target", "Nastawa bezwzględna stężenia pyłu", 54, "µg/m³", 0, 200),
            ("pm10_reference", "Stężenie odniesienia PM10", 52, "µg/m³", 10, 300),
            ("pm25_reference", "Stężenie odniesienia PM2.5", 57, "µg/m³", 10, 300),
        )]
    if platform == "time":
        return [ParticleFilterCheckTime(coordinator, entry)]
    if platform == "button":
        return [ParticleCommandButton(coordinator, entry, *definition) for definition in (
            ("check_filters", "Uruchom kontrolę filtrów", FILTER_PROCEDURE_REGISTER, START_FILTER_CHECK,
             lambda raw: raw.get(42) == 0 and raw.get(4398) not in FILTER_BUSY_MESSAGES),
            ("acknowledge_filter_message", "Potwierdź komunikat filtrów", FILTER_MESSAGE_REGISTER, 0,
             lambda raw: raw.get(4398) in FILTER_MESSAGES and raw.get(4398) != 0
             and raw.get(4398) not in FILTER_QUESTIONS | FILTER_CRITICAL_MESSAGES | FILTER_BUSY_MESSAGES),
            ("accept_filter", "Użyj filtra o większym oporze — TAK", FILTER_ANSWER_REGISTER, 1,
             lambda raw: raw.get(4398) in FILTER_QUESTIONS),
            ("reject_filter", "Użyj filtra o większym oporze — NIE", FILTER_ANSWER_REGISTER, 0,
             lambda raw: raw.get(4398) in FILTER_QUESTIONS),
            ("reset_fan_alarm", "Skasuj alarm wentylatora S2", 97, 0,
             lambda raw: bool(raw.get(96, 0) & 0x0001)),
            ("reset_eeprom_alarm", "Skasuj alarm EEPROM S255", 97, 3,
             lambda raw: bool(raw.get(96, 0) & 0x0008)),
        )]
    raise ValueError(f"Unknown Particle+ platform: {platform}")
