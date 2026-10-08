"""Serialized Modbus reads and writes for recuperators and Particle+."""

import asyncio
import logging
import time
from dataclasses import dataclass, field as dataclass_field

from pymodbus.client import AsyncModbusTcpClient

from .const import (
    DEVICE_PARTICLE,
    DEVICE_REKUPERATOR,
    DEVICE_AIRPACK4,
    PARTICLE_EXTENDED_ALARMS_VERSION,
    PARTICLE_FIRMWARE_REGISTER,
    PARTICLE_HOLDING_BLOCKS,
)
from .airpack4_registers import (
    REQUIRED_HOLDING, OPTIONAL_HOLDING, SCHEDULE_REGISTERS,
    INPUT_REGISTERS, COIL_REGISTERS, DISCRETE_REGISTERS, register_blocks,
)
from .particle_registers import OPTIONAL_BLOCKS, MODERN_BLOCKS, HISTORY_BLOCKS, MODERN_HISTORY_BLOCKS

_LOGGER = logging.getLogger(__name__)


@dataclass
class ControllerData:
    holding: dict[int, int] = dataclass_field(default_factory=dict)
    input: dict[int, int] = dataclass_field(default_factory=dict)
    coil: dict[int, bool] = dataclass_field(default_factory=dict)
    discrete: dict[int, bool] = dataclass_field(default_factory=dict)
    update_interval: float = 0.0


class ControllerException(Exception):
    """A connection, protocol or response validation failure."""


class UnsupportedRegister(ControllerException):
    """The device explicitly returned Modbus Illegal Data Address."""


class ThesslaGreenModbusController:
    def __init__(self, host: str, port: int, slave_id: int, update_interval: int = 30,
                 device_type: str = DEVICE_REKUPERATOR):
        if device_type not in (DEVICE_REKUPERATOR, DEVICE_PARTICLE, DEVICE_AIRPACK4):
            raise ValueError(f"Unknown device type: {device_type}")
        self._host = host
        self._port = port
        self._slave = slave_id
        self._device_type = device_type
        self._client = AsyncModbusTcpClient(
            host=host, port=port, reconnect_delay=1, reconnect_delay_max=300,
            timeout=3, retries=2,
        )
        self._controller_lock = asyncio.Lock()
        self._last_update_timestamp: float | None = None
        self._unsupported_registers = set()
        self._schedule_cache = {}
        self._schedule_timestamp = None
        self._particle_history_cache = {}
        self._particle_history_timestamp = None
        self._holding_blocks = [
            (256, 2), (4192, 1), (4198, 1), (4208, 3), (4224, 1),
            (4320, 1), (4387, 1), (8192, 2), (8208, 1), (8222, 2),
            (8330, 2), (4704, 1), (4711, 1), (8444, 1), (4304, 2),
        ]
        self._input_blocks = [(16, 4), (22, 1)]
        self._coil_blocks = [(9, 3)]
        if device_type == DEVICE_PARTICLE:
            self._holding_blocks = list(PARTICLE_HOLDING_BLOCKS)
            self._input_blocks = []
            self._coil_blocks = []

    async def stop(self):
        async with self._controller_lock:
            self._client.close()

    async def _read_values(self, read_method, start, count, kind, field="registers"):
        try:
            result = await read_method(address=start, count=count, device_id=self._slave)
            if result.isError():
                if getattr(result, "exception_code", None) == 2:
                    raise UnsupportedRegister(f"Unsupported {kind} at {start}")
                raise ControllerException(f"Error reading {kind} {start}-{start + count - 1}: {result}")
            values = getattr(result, field)
            if len(values) < count or (field == "registers" and len(values) != count):
                raise ControllerException(f"Incomplete {kind} response at {start}")
            # Modbus pads coil responses to complete bytes.
            values = values[:count]
            _LOGGER.debug("%s %d-%d: %s", kind, start, start + count - 1, values)
            return values
        except ControllerException:
            raise
        except Exception as error:
            raise ControllerException(f"Exception reading {kind} at {start}: {error}") from error

    async def fetch_data(self) -> ControllerData:
        async with self._controller_lock:
            await self._ensure_connected()
            now = time.monotonic()
            data = ControllerData()
            if self._device_type == DEVICE_AIRPACK4:
                await self._fetch_airpack4(data, now)
                if self._last_update_timestamp is not None:
                    data.update_interval = round(now - self._last_update_timestamp, 2)
                self._last_update_timestamp = now
                return data
            for blocks, read_method, target, kind, field in (
                (self._holding_blocks, self._client.read_holding_registers, data.holding, "holding registers", "registers"),
                (self._input_blocks, self._client.read_input_registers, data.input, "input registers", "registers"),
                (self._coil_blocks, self._client.read_coils, data.coil, "coils", "bits"),
            ):
                for start, count in blocks:
                    values = await self._read_values(read_method, start, count, kind, field)
                    target.update({start + index: bool(value) if field == "bits" else value
                                   for index, value in enumerate(values)})
            if self._device_type == DEVICE_PARTICLE:
                await self._fetch_particle_information(data, now)
            if self._last_update_timestamp is not None:
                data.update_interval = round(now - self._last_update_timestamp, 2)
            self._last_update_timestamp = now
            return data

    async def write_register(self, address: int, value: int) -> bool:
        async with self._controller_lock:
            await self._ensure_connected()
            try:
                result = await self._client.write_register(address=address, value=value, device_id=self._slave)
                if result.isError():
                    raise ControllerException(f"Failed to write register {address} with value {value}")
                _LOGGER.debug("Wrote register %d = %s", address, value)
                self._schedule_timestamp = None
                self._particle_history_timestamp = None
                return True
            except ControllerException:
                raise
            except Exception as error:
                raise ControllerException(f"Exception writing register {address} = {value}: {error}") from error

    async def write_registers(self, address: int, values: list[int]) -> bool:
        """Write coupled fields in one FC16 transaction (at most 16 registers)."""
        if not values or len(values) > 16 or any(
                not isinstance(value, int) or not 0 <= value <= 0xFFFF for value in values):
            raise ControllerException("Invalid register block values")
        async with self._controller_lock:
            await self._ensure_connected()
            try:
                result = await self._client.write_registers(address=address, values=values, device_id=self._slave)
                if result.isError():
                    raise ControllerException(f"Failed to write registers at {address}")
                self._schedule_timestamp = None
                return True
            except ControllerException:
                raise
            except Exception as error:
                raise ControllerException(f"Exception writing registers at {address}: {error}") from error

    async def _read_optional_block(self, method, start, count, target, kind, field="registers"):
        missing = self._unsupported_registers
        if count == 1 and (kind, start) in missing:
            return
        if any((kind, address) in missing for address in range(start, start + count)):
            for address in range(start, start + count):
                await self._read_optional_block(method, address, 1, target, kind, field)
            return
        try:
            values = await self._read_values(method, start, count, kind, field)
        except UnsupportedRegister:
            if count == 1:
                missing.add((kind, start))
                _LOGGER.debug("Skipping unsupported optional %s %d", kind, start)
            else:
                for address in range(start, start + count):
                    await self._read_optional_block(method, address, 1, target, kind, field)
            return
        target.update({start + index: bool(value) if field == "bits" else value
                       for index, value in enumerate(values)})

    async def update_register(self, address: int, mask: int, value: int) -> bool:
        """Preserve the other packed field, including concurrent HA commands."""
        if not 0 < mask <= 0xFFFF or not 0 <= value <= 0xFFFF or value & ~mask:
            raise ControllerException("Invalid packed register update")
        async with self._controller_lock:
            await self._ensure_connected()
            current = (await self._read_values(self._client.read_holding_registers, address, 1, "holding registers"))[0]
            updated = (current & ~mask) | value
            try:
                result = await self._client.write_register(address=address, value=updated, device_id=self._slave)
                if result.isError():
                    raise ControllerException(f"Failed to update register {address}")
                self._schedule_timestamp = None
                return True
            except ControllerException:
                raise
            except Exception as error:
                raise ControllerException(f"Exception updating register {address}: {error}") from error

    async def _fetch_airpack4(self, data, now):
        for start, count in register_blocks(REQUIRED_HOLDING):
            values = await self._read_values(self._client.read_holding_registers, start, count, "holding registers")
            data.holding.update({start + index: value for index, value in enumerate(values)})
        for addresses, method, target, kind, field in (
            (OPTIONAL_HOLDING, self._client.read_holding_registers, data.holding, "holding registers", "registers"),
            (INPUT_REGISTERS, self._client.read_input_registers, data.input, "input registers", "registers"),
            (COIL_REGISTERS, self._client.read_coils, data.coil, "coils", "bits"),
            (DISCRETE_REGISTERS, self._client.read_discrete_inputs, data.discrete, "discrete inputs", "bits"),
        ):
            for start, count in register_blocks(addresses):
                await self._read_optional_block(method, start, count, target, kind, field)
        if self._schedule_timestamp is None or now - self._schedule_timestamp >= 300:
            schedule = {}
            for start, count in register_blocks(SCHEDULE_REGISTERS):
                await self._read_optional_block(self._client.read_holding_registers, start, count,
                                                schedule, "holding registers")
            self._schedule_cache = schedule
            self._schedule_timestamp = now
        data.holding.update(self._schedule_cache)

    async def _fetch_particle_information(self, data, now):
        modern = data.holding[PARTICLE_FIRMWARE_REGISTER] >= PARTICLE_EXTENDED_ALARMS_VERSION
        # The RTC must be read as one four-word snapshot, even when unsupported.
        if not any(("holding registers", address) in self._unsupported_registers for address in range(4)):
            try:
                clock = await self._read_values(self._client.read_holding_registers, 0, 4, "holding registers")
            except UnsupportedRegister:
                self._unsupported_registers.update(("holding registers", address) for address in range(4))
            else:
                data.holding.update(enumerate(clock))
        for start, count in OPTIONAL_BLOCKS + (MODERN_BLOCKS if modern else ()):
            await self._read_optional_block(self._client.read_holding_registers, start, count,
                                            data.holding, "holding registers")
        if self._particle_history_timestamp is None or now - self._particle_history_timestamp >= 300:
            history = {}
            for start, count in HISTORY_BLOCKS + (MODERN_HISTORY_BLOCKS if modern else ()):
                await self._read_optional_block(self._client.read_holding_registers, start, count,
                                                history, "holding registers")
            self._particle_history_cache = history
            self._particle_history_timestamp = now
        data.holding.update(self._particle_history_cache)

    async def _ensure_connected(self):
        if self._client.connected:
            return
        try:
            if await self._client.connect():
                return
        except Exception as error:
            raise ControllerException(f"Exception connecting to {self._host}:{self._port}: {error}") from error
        raise ControllerException(f"Failed to connect to Modbus server {self._host}:{self._port}")
