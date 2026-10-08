"""Verify Particle+ measurements and commands using real HA entity classes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.thessla_green.modbus_controller import ControllerData, ControllerException
from custom_components.thessla_green.particle import is_particle, particle_entities


@pytest.fixture
def entry():
    return SimpleNamespace(entry_id="particle-one", data={"device_type": "particle"})


@pytest.fixture
def coordinator():
    return SimpleNamespace(
        last_update_success=True,
        safe_data=ControllerData(holding={
            16: 1, 17: 0, 33: 65526, 36: 100, 41: 0, 48: 1,
            50: 500, 51: 2, 52: 50, 53: 0, 54: 5, 56: 5, 57: 25,
            64: 40, 65: 30, 96: 0xA020, 4114: 150, 4115: 200,
        }),
        controller=SimpleNamespace(write_register=AsyncMock(return_value=True)),
        async_request_refresh=AsyncMock(),
    )


def test_measurements_and_missing_data(coordinator, entry):
    sensors = {entity._address: entity for entity in particle_entities("sensor", coordinator, entry)}
    assert sensors[33].native_value == -10
    assert sensors[50].native_value == 500
    assert sensors[50].extra_state_attributes == {"particle_type": "PM2.5"}
    coordinator.safe_data.holding[48] = 0
    assert sensors[50].extra_state_attributes == {"particle_type": "PM10"}
    assert sensors[4115].native_value == 200
    del coordinator.safe_data.holding[50]
    assert sensors[50].native_value is None
    assert not sensors[50].available
    coordinator.last_update_success = False
    assert not sensors[33].available


def test_alarm_masks(coordinator, entry):
    alarms = {e._attr_unique_id.rsplit("particle-one_", 1)[1]: e
              for e in particle_entities("binary_sensor", coordinator, entry)}
    assert alarms["alarm"].is_on
    assert alarms["hepa_replace"].is_on
    assert not alarms["prefilter_replace"].is_on
    assert not alarms["fan_fault"].is_on
    coordinator.safe_data.holding[96] = 0x0201
    assert alarms["fan_fault"].is_on
    assert alarms["prefilter_replace"].is_on
    assert not alarms["hepa_replace"].is_on
    del coordinator.safe_data.holding[96]
    assert alarms["alarm"].is_on is None


def test_extended_particle_alarms(coordinator, entry):
    coordinator.safe_data.holding.update({8131: 0x0304, 96: 0, 98: 0x0006})
    alarms = {e._attr_unique_id.rsplit("particle-one_", 1)[1]: e
              for e in particle_entities("binary_sensor", coordinator, entry)}
    assert alarms["alarm"].is_on
    assert alarms["prefilter_missing"].is_on
    assert alarms["hepa_missing"].is_on
    assert not alarms["permission_missing"].is_on
    coordinator.safe_data.holding[98] = 1
    assert alarms["permission_missing"].is_on
    del coordinator.safe_data.holding[98]
    assert not alarms["alarm"].available


@pytest.mark.asyncio
async def test_controls_write_and_refresh(coordinator, entry):
    power = particle_entities("switch", coordinator, entry)[0]
    await power.async_turn_on()
    coordinator.controller.write_register.assert_awaited_with(16, 1)
    await power.async_turn_off()
    coordinator.controller.write_register.assert_awaited_with(16, 0)
    mode, kind, regulation = particle_entities("select", coordinator, entry)[:3]
    assert mode.current_option == "Manualny"
    await mode.async_select_option("Automatyczny")
    coordinator.controller.write_register.assert_awaited_with(17, 1)
    await kind.async_select_option("PM10")
    coordinator.controller.write_register.assert_awaited_with(48, 0)
    await regulation.async_select_option("Względny")
    coordinator.controller.write_register.assert_awaited_with(53, 1)
    intensity = particle_entities("number", coordinator, entry)[0]
    await intensity.async_set_native_value(10)
    coordinator.controller.write_register.assert_awaited_with(65, 10)
    assert coordinator.async_request_refresh.await_count == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, 9, 101, 10.5, float("nan"), float("inf")])
async def test_invalid_intensity_never_written(coordinator, entry, value):
    intensity = particle_entities("number", coordinator, entry)[0]
    with pytest.raises(HomeAssistantError):
        await intensity.async_set_native_value(value)
    coordinator.controller.write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_write_errors_and_unknown_options(coordinator, entry):
    mode = particle_entities("select", coordinator, entry)[0]
    with pytest.raises(HomeAssistantError):
        await mode.async_select_option("Unsupported")
    coordinator.controller.write_register.assert_not_awaited()
    coordinator.controller.write_register.side_effect = ControllerException("Timeout")
    with pytest.raises(HomeAssistantError, match="Timeout"):
        await mode.async_select_option("Manualny")
    coordinator.async_request_refresh.assert_not_awaited()


def test_particle_identity_does_not_collide(coordinator, entry):
    one = particle_entities("switch", coordinator, entry)[0]
    two = particle_entities("switch", coordinator,
                            SimpleNamespace(entry_id="particle-two", data=entry.data))[0]
    assert one.unique_id != two.unique_id
    assert one.device_info["identifiers"] != two.device_info["identifiers"]
    assert not is_particle(SimpleNamespace(data={}))
    assert not is_particle(SimpleNamespace(data={"device_type": "rekuperator"}))
