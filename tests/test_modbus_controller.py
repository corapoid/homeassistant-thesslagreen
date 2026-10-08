"""Exercise protocol requests and failure paths without a physical gateway."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.thessla_green.modbus_controller import (
    ControllerException, ThesslaGreenModbusController,
)


@pytest.fixture
def client():
    with patch("custom_components.thessla_green.modbus_controller.AsyncModbusTcpClient") as factory:
        client = factory.return_value
        client.connected = True
        client.read_holding_registers = AsyncMock(side_effect=lambda **kwargs: SimpleNamespace(
            isError=lambda: False, registers=list(range(kwargs["count"])),
        ))
        client.read_input_registers = AsyncMock()
        client.read_coils = AsyncMock()
        client.write_register = AsyncMock(return_value=SimpleNamespace(isError=lambda: False))
        yield client


@pytest.mark.asyncio
async def test_particle_requests(client):
    controller = ThesslaGreenModbusController("gateway", 502, 30, device_type="particle")
    data = await controller.fetch_data()
    requests = [call.kwargs for call in client.read_holding_registers.await_args_list]
    assert {(call["address"], call["count"]) for call in requests} == {
        (16, 2), (33, 1), (36, 1), (41, 1), (48, 1), (50, 5),
        (56, 2), (64, 2), (96, 1), (4114, 2), (8131, 1),
        (0, 4), (42, 3), (55, 1), (97, 1), (112, 10), (4398, 3), (8128, 3), (8144, 1),
        (1536, 16), (1552, 16), (1568, 16), (1584, 16),
    }
    assert all(call["device_id"] == 30 and call["count"] <= 16 for call in requests)
    assert data.holding[17] == 1
    assert not data.input and not data.coil
    client.read_input_registers.assert_not_awaited()
    client.read_coils.assert_not_awaited()
    await controller.write_register(65, 30)
    client.write_register.assert_awaited_once_with(address=65, value=30, device_id=30)
    await controller.stop()
    client.close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("firmware,extended", [(0x0303, False), (0x0304, True), (0x0400, True)])
async def test_particle_alarm_register_depends_on_firmware(client, firmware, extended):
    def response(**kwargs):
        address = kwargs["address"]
        return SimpleNamespace(isError=lambda: False, registers=[
            firmware if address + index == 8131 else 4 if address + index == 98 else 0
            for index in range(kwargs["count"])
        ])
    client.read_holding_registers.side_effect = response
    controller = ThesslaGreenModbusController("gateway", 502, 30, device_type="particle")
    data = await controller.fetch_data()
    assert data.holding[8131] == firmware
    assert (98 in data.holding) == extended
    if extended:
        assert data.holding[98] == 4
    requests = client.read_holding_registers.await_args_list
    assert any(call.kwargs["address"] == 8132 for call in requests) == extended
    assert any(call.kwargs["address"] == 1600 for call in requests) == extended


@pytest.mark.asyncio
async def test_particle_optional_message_failure_and_rtc_snapshot(client):
    reads = []

    def response(**kwargs):
        start, count = kwargs["address"], kwargs["count"]
        reads.append((start, count))
        if start == 0 or start <= 4398 < start + count:
            return SimpleNamespace(isError=lambda: True, exception_code=2)
        return SimpleNamespace(isError=lambda: False, registers=[0] * count)

    client.read_holding_registers.side_effect = response
    controller = ThesslaGreenModbusController("gateway", 502, 30, device_type="particle")
    data = await controller.fetch_data()
    assert 4398 not in data.holding and data.holding[4399] == 0
    assert (0, 4) in reads and (0, 1) not in reads
    assert all(address not in data.holding for address in range(4))
    reads.clear()
    await controller.fetch_data()
    assert not any(start in (0, 4398) for start, count in reads)


@pytest.mark.asyncio
async def test_particle_optional_device_failure_is_not_ignored(client):
    def response(**kwargs):
        if kwargs["address"] == 4398:
            return SimpleNamespace(isError=lambda: True, exception_code=4)
        return SimpleNamespace(isError=lambda: False, registers=[0] * kwargs["count"])

    client.read_holding_registers.side_effect = response
    with pytest.raises(ControllerException):
        await ThesslaGreenModbusController("gateway", 502, 30, device_type="particle").fetch_data()


@pytest.mark.asyncio
async def test_particle_history_cache_refreshes_after_command(client):
    controller = ThesslaGreenModbusController("gateway", 502, 30, device_type="particle")
    await controller.fetch_data()
    client.read_holding_registers.reset_mock()
    await controller.fetch_data()
    assert not any(1536 <= call.kwargs["address"] <= 1611
                   for call in client.read_holding_registers.await_args_list)
    await controller.write_register(42, 3)
    client.read_holding_registers.reset_mock()
    await controller.fetch_data()
    assert any(call.kwargs["address"] == 1536 for call in client.read_holding_registers.await_args_list)


def test_legacy_profile(client):
    controller = ThesslaGreenModbusController("gateway", 8899, 10)
    assert (4208, 3) in controller._holding_blocks
    assert controller._input_blocks == [(16, 4), (22, 1)]
    assert controller._coil_blocks == [(9, 3)]
    assert (4210, 1) not in controller._holding_blocks


def legacy_responses(client):
    client.read_input_registers.side_effect = lambda **kwargs: SimpleNamespace(
        isError=lambda: False, registers=[0] * kwargs["count"],
    )
    client.read_coils.return_value = SimpleNamespace(isError=lambda: False, bits=[True, False, True, False, False, False, False, False])


@pytest.mark.asyncio
async def test_coil_padding_is_not_exposed(client):
    legacy_responses(client)
    data = await ThesslaGreenModbusController("gateway", 502, 10).fetch_data()
    assert data.coil == {9: True, 10: False, 11: True}


@pytest.mark.asyncio
async def test_incomplete_input_response_fails(client):
    legacy_responses(client)
    client.read_input_registers.side_effect = None
    client.read_input_registers.return_value = SimpleNamespace(isError=lambda: False, registers=[1])
    with pytest.raises(ControllerException, match="Incomplete"):
        await ThesslaGreenModbusController("gateway", 502, 10).fetch_data()


@pytest.mark.asyncio
async def test_update_interval_uses_monotonic_clock(client):
    controller = ThesslaGreenModbusController("gateway", 502, 30, device_type="particle")
    with patch("custom_components.thessla_green.modbus_controller.time.monotonic", side_effect=[100.0, 130.0]), \
            patch("custom_components.thessla_green.modbus_controller.time.time", side_effect=[1000.0, 500.0]):
        assert (await controller.fetch_data()).update_interval == 0
        assert (await controller.fetch_data()).update_interval == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    SimpleNamespace(isError=lambda: True),
    SimpleNamespace(isError=lambda: False, registers=[1]),
])
async def test_bad_read_response(client, response):
    controller = ThesslaGreenModbusController("gateway", 502, 30, device_type="particle")
    client.read_holding_registers.side_effect = None
    client.read_holding_registers.return_value = response
    with pytest.raises(ControllerException):
        await controller.fetch_data()


@pytest.mark.asyncio
async def test_connection_and_write_failure(client):
    controller = ThesslaGreenModbusController("gateway", 502, 30, device_type="particle")
    client.connected = False
    client.connect = AsyncMock(return_value=False)
    with pytest.raises(ControllerException, match="Failed to connect"):
        await controller.fetch_data()
    client.connected = True
    client.write_register.return_value = SimpleNamespace(isError=lambda: True)
    with pytest.raises(ControllerException, match="Failed to write"):
        await controller.write_register(16, 1)
