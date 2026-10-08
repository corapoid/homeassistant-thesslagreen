"""Verify filter messages, individual alarms and explicit Particle+ commands."""

from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.thessla_green.modbus_controller import ControllerData, ControllerException
from custom_components.thessla_green.particle import particle_entities


@pytest.fixture
def entry():
    return SimpleNamespace(entry_id="particle", data={"device_type": "particle"})


@pytest.fixture
def coordinator():
    return SimpleNamespace(last_update_success=True, safe_data=ControllerData(holding={
        16: 1, 17: 0, 41: 0, 42: 0, 43: 0, 44: 0x0C1E, 55: 50,
        96: 0x0100, 97: 0, 98: 0, 4398: 0x47, 4399: 0, 4400: 0,
        8128: 0x1A2B, 8129: 0x3C4D, 8130: 0x5E6F, 8131: 0x0304, 8132: 2,
        8192: 0, 8193: 1, 12352: 1,
    }), controller=SimpleNamespace(write_register=AsyncMock(return_value=True)),
        async_request_refresh=AsyncMock())


def by_key(platform, coordinator, entry):
    return {entity._key: entity for entity in particle_entities(platform, coordinator, entry)}


@pytest.mark.parametrize("code,text", [
    (0x31, "Wykryto nowy filtr HEPA"),
    (0x39, "Filtr HEPA ma większy opór niż oryginalny — użyć filtra?"),
    (0x47, "Kontrola filtrów — błąd przepływu"),
    (0x48, "Procedura kontroli filtrów zakończona"),
    (0, "Brak komunikatu"),
])
def test_filter_message_and_independent_s116(coordinator, entry, code, text):
    coordinator.safe_data.holding[4398] = code
    sensors = by_key("sensor", coordinator, entry)
    assert sensors["filter_message"].native_value == text
    assert sensors["filter_message"].extra_state_attributes["code_hex"] == f"0x{code:02X}"
    assert sensors["filter_message_code"].native_value == code
    assert by_key("binary_sensor", coordinator, entry)["alarm_s116"].is_on
    # Completion is not evidence that an independent automatic alarm was reset.
    coordinator.controller.write_register.assert_not_awaited()


def test_unknown_message_preserves_code(coordinator, entry):
    coordinator.safe_data.holding[4398] = 0xABCD
    sensor = by_key("sensor", coordinator, entry)["filter_message"]
    assert "0xABCD" in sensor.native_value
    assert sensor.extra_state_attributes["code"] == 0xABCD


@pytest.mark.asyncio
async def test_filter_check_writes_only_documented_command(coordinator, entry):
    button = by_key("button", coordinator, entry)["check_filters"]
    assert button.available
    await button.async_press()
    coordinator.controller.write_register.assert_awaited_once_with(42, 3)
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure,message", [(3, 0), (0, 0x42), (0, 0x43), (1, 0)])
async def test_busy_procedure_cannot_be_restarted(coordinator, entry, procedure, message):
    coordinator.safe_data.holding.update({42: procedure, 4398: message})
    button = by_key("button", coordinator, entry)["check_filters"]
    assert not button.available
    with pytest.raises(HomeAssistantError):
        await button.async_press()
    coordinator.controller.write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_acknowledgement_and_filter_answers_are_explicit(coordinator, entry):
    buttons = by_key("button", coordinator, entry)
    await buttons["acknowledge_filter_message"].async_press()
    coordinator.controller.write_register.assert_awaited_with(4398, 0)
    coordinator.safe_data.holding[4398] = 0x39
    assert not buttons["acknowledge_filter_message"].available
    with pytest.raises(HomeAssistantError):
        await buttons["acknowledge_filter_message"].async_press()
    await buttons["accept_filter"].async_press()
    coordinator.controller.write_register.assert_awaited_with(4400, 1)
    await buttons["reject_filter"].async_press()
    coordinator.controller.write_register.assert_awaited_with(4400, 0)
    coordinator.safe_data.holding[4398] = 0x38
    assert not buttons["acknowledge_filter_message"].available
    assert not buttons["accept_filter"].available


@pytest.mark.asyncio
async def test_failed_filter_command_is_reported(coordinator, entry):
    coordinator.controller.write_register.side_effect = ControllerException("offline")
    with pytest.raises(HomeAssistantError, match="offline"):
        await by_key("button", coordinator, entry)["check_filters"].async_press()
    coordinator.async_request_refresh.assert_not_awaited()


def test_measured_particle_metadata(coordinator, entry):
    sensors = by_key("sensor", coordinator, entry)
    assert sensors["firmware"].native_value == "3.4.2"
    assert sensors["serial"].native_value == "1a2b3c4d5e6f"
    assert sensors["firmware"].device_info["sw_version"] == "3.4.2"
    assert sensors["firmware"].device_info["serial_number"] == "1a2b3c4d5e6f"


@pytest.mark.asyncio
async def test_particle_check_clock_uses_byte_fields(coordinator, entry):
    clock = by_key("time", coordinator, entry)["filter_check_time"]
    assert clock.native_value == time(12, 30)
    await clock.async_set_value(time(22, 45))
    coordinator.controller.write_register.assert_awaited_with(44, 0x162D)
    with pytest.raises(HomeAssistantError):
        await clock.async_set_value(time(22, 45, 1))


@pytest.mark.asyncio
async def test_user_reset_codes_do_not_clear_s116(coordinator, entry):
    coordinator.safe_data.holding[96] = 0x0009
    buttons = by_key("button", coordinator, entry)
    await buttons["reset_fan_alarm"].async_press()
    coordinator.controller.write_register.assert_awaited_with(97, 0)
    await buttons["reset_eeprom_alarm"].async_press()
    coordinator.controller.write_register.assert_awaited_with(97, 3)
    assert "reset_s116" not in buttons


def test_alarm_summary_and_record_words(coordinator, entry):
    coordinator.safe_data.holding.update({
        96: 0x010A, 98: 2, 1568: 0x1A0A, 1569: 0x0809, 1570: 0x0A0B, 1571: 1,
    })
    sensors = by_key("sensor", coordinator, entry)
    assert sensors["active_alarms"].extra_state_attributes["alarm_descriptions"] == {
        "E8": "Brak odczytu PmSensor OUT", "S255": "Błąd komunikacji EEPROM",
        "S116": "Konieczna wymiana filtra HEPA", "S117": "Brak filtra wstępnego",
    }
    history = sensors["history_s116"]
    assert history.available
    assert history.extra_state_attributes["packed_words_hex"] == ["0x1A0A", "0x0809", "0x0A0B", "0x0001"]
    coordinator.safe_data.holding[8131] = 0x0303
    sensors = by_key("sensor", coordinator, entry)
    assert "S8" in sensors["active_alarms"].native_value
    assert "history_s117" not in sensors


def test_missing_diagnostics_are_unavailable_and_ids_are_unique(coordinator, entry):
    for platform in ("sensor", "binary_sensor", "select", "number", "switch", "button", "time"):
        entities = particle_entities(platform, coordinator, entry)
        assert len(entities) == len({entity.unique_id for entity in entities})
        assert all(not entity.should_poll for entity in entities)
    del coordinator.safe_data.holding[4398]
    sensors = by_key("sensor", coordinator, entry)
    assert not sensors["filter_message"].available
    assert sensors["filter_message"].native_value is None
    assert not by_key("button", coordinator, entry)["acknowledge_filter_message"].available
