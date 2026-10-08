"""Check config schemas and platform routing for Particle+ and legacy entries."""

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryNotReady
import voluptuous as vol

from custom_components.thessla_green.config_flow import ThesslaGreenConfigFlow
from custom_components.thessla_green.const import DOMAIN, DEVICE_AIRPACK4
from custom_components.thessla_green.modbus_controller import ControllerData
from custom_components.thessla_green.options_flow import ThesslaGreenOptionsFlowHandler


@pytest.mark.asyncio
@pytest.mark.parametrize("device_type,slave", [("particle", 30), ("rekuperator", 10), (DEVICE_AIRPACK4, 10)])
async def test_device_config(device_type, slave):
    flow = ThesslaGreenConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    initial = await flow.async_step_user()
    assert initial["data_schema"]({}) == {"device_type": "rekuperator"}
    result = await flow.async_step_user({"device_type": device_type})
    assert result["step_id"] == "connection"
    data = result["data_schema"]({"host": "192.0.2.1"})
    assert data["slave"] == slave
    with pytest.raises(vol.Invalid):
        result["data_schema"]({"host": "gateway", "scan_interval": 0})
    with pytest.raises(vol.Invalid):
        result["data_schema"]({"host": "gateway", "slave": 248})
    with pytest.raises(vol.Invalid):
        result["data_schema"]({"host": "gateway", "port": 65536})
    created = await flow.async_step_connection(data)
    assert created["data"]["device_type"] == device_type
    assert created["data"]["slave"] == slave
    flow.async_set_unique_id.assert_awaited_once_with(f"{device_type}_192.0.2.1_8899_{slave}")
    flow._abort_if_unique_id_configured.assert_called_once()


@pytest.mark.asyncio
async def test_particle_options_do_not_require_power():
    entry = SimpleNamespace(data={"device_type": "particle"})
    flow = ThesslaGreenOptionsFlowHandler(entry)
    result = await flow.async_step_init()
    assert result["data_schema"]({}) == {}
    assert (await flow.async_step_init({}))["data"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("platform,particle_count,legacy_count", [
    ("sensor", 45, 13), ("binary_sensor", 26, 15), ("switch", 1, 3),
    ("select", 5, 4), ("number", 4, 1),
])
@pytest.mark.parametrize("particle", [False, True])
async def test_platform_routes_to_correct_entities(platform, particle_count, legacy_count, particle):
    module = import_module(f"custom_components.thessla_green.{platform}")
    coordinator = SimpleNamespace(last_update_success=True, safe_data=ControllerData())
    entry = SimpleNamespace(entry_id="entry", data={"device_type": "particle"} if particle else {}, options={})
    hass = SimpleNamespace(data={DOMAIN: {"entry": {"coordinator": coordinator, "slave": 30}}})
    add = MagicMock()
    await module.async_setup_entry(hass, entry, add)
    entities = add.call_args.args[0]
    assert len(entities) == (particle_count if particle else legacy_count)
    assert all(entity.unique_id.startswith("thessla_particle_") == particle for entity in entities)


@pytest.mark.asyncio
@pytest.mark.parametrize("device_type", [None, "particle", DEVICE_AIRPACK4])
async def test_setup_controller_profile_and_unload(device_type):
    integration = import_module("custom_components.thessla_green")
    data = {"host": "gateway", "port": 502, "slave": 30}
    if device_type:
        data["device_type"] = device_type
    entry = MagicMock(entry_id="entry", data=data)
    hass = SimpleNamespace(data={}, config_entries=SimpleNamespace(
        async_forward_entry_setups=AsyncMock(), async_unload_platforms=AsyncMock(return_value=True),
    ))
    with patch.object(integration, "ThesslaGreenModbusController") as factory, \
            patch.object(integration, "ThesslaGreenCoordinator") as coordinator:
        factory.return_value.stop = AsyncMock()
        coordinator.return_value.async_config_entry_first_refresh = AsyncMock()
        assert await integration.async_setup_entry(hass, entry)
        assert factory.call_args.kwargs["device_type"] == (device_type or "rekuperator")
        hass.config_entries.async_forward_entry_setups.assert_awaited_once()
        assert await integration.async_unload_entry(hass, entry)
        factory.return_value.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_initial_read_closes_client():
    integration = import_module("custom_components.thessla_green")
    entry = SimpleNamespace(entry_id="entry", data={
        "host": "gateway", "port": 502, "slave": 30, "device_type": "particle",
    })
    hass = SimpleNamespace(data={})
    with patch.object(integration, "ThesslaGreenModbusController") as factory, \
            patch.object(integration, "ThesslaGreenCoordinator") as coordinator:
        factory.return_value.stop = AsyncMock()
        coordinator.return_value.async_config_entry_first_refresh = AsyncMock(side_effect=ConfigEntryNotReady("Timeout"))
        with pytest.raises(ConfigEntryNotReady):
            await integration.async_setup_entry(hass, entry)
        factory.return_value.stop.assert_awaited_once()
        assert "entry" not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_failed_unload_retains_controller():
    integration = import_module("custom_components.thessla_green")
    controller = SimpleNamespace(stop=AsyncMock())
    hass = SimpleNamespace(data={DOMAIN: {"entry": {"controller": controller}}},
                           config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=False)))
    assert not await integration.async_unload_entry(hass, SimpleNamespace(entry_id="entry"))
    assert hass.data[DOMAIN]["entry"]["controller"] is controller
    controller.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_options_listener_reloads_entry():
    integration = import_module("custom_components.thessla_green")
    entry = MagicMock(entry_id="entry", data={"host": "gateway", "port": 502, "slave": 10})
    hass = SimpleNamespace(data={}, config_entries=SimpleNamespace(
        async_forward_entry_setups=AsyncMock(), async_reload=AsyncMock(),
    ))
    with patch.object(integration, "ThesslaGreenModbusController"), \
            patch.object(integration, "ThesslaGreenCoordinator") as coordinator:
        coordinator.return_value.async_config_entry_first_refresh = AsyncMock()
        assert await integration.async_setup_entry(hass, entry)
    listener = entry.add_update_listener.call_args.args[0]
    await listener(hass, entry)
    hass.config_entries.async_reload.assert_awaited_once_with("entry")
    entry.async_on_unload.assert_called_once_with(entry.add_update_listener.return_value)


@pytest.mark.asyncio
async def test_power_sensor_can_be_cleared():
    flow = ThesslaGreenOptionsFlowHandler(SimpleNamespace(data={}, options={"sensor_power": "sensor.old"}))
    flow.hass = SimpleNamespace(states=SimpleNamespace(get=lambda _: None))
    result = await flow.async_step_init({})
    assert result["type"] == "create_entry"
    assert result["data"] == {}


@pytest.mark.asyncio
async def test_options_can_enable_airpack4_profile():
    flow = ThesslaGreenOptionsFlowHandler(SimpleNamespace(data={}, options={}))
    flow.hass = SimpleNamespace(states=SimpleNamespace(get=lambda _: None))
    result = await flow.async_step_init({"recuperator_model": DEVICE_AIRPACK4, "filter_control": "afc_both"})
    assert result["data"] == {"recuperator_model": DEVICE_AIRPACK4, "filter_control": "afc_both"}


@pytest.mark.asyncio
@pytest.mark.parametrize("unit,error", [("W", None), ("kW", None), ("Wh", "invalid_power_unit"), (None, "invalid_power_unit")])
async def test_power_sensor_unit_validation(unit, error):
    flow = ThesslaGreenOptionsFlowHandler(SimpleNamespace(data={}, options={}))
    flow.hass = SimpleNamespace(states=SimpleNamespace(get=lambda _: SimpleNamespace(
        attributes={"unit_of_measurement": unit},
    )))
    result = await flow.async_step_init({"sensor_power": "sensor.power"})
    if error:
        assert result["errors"] == {"sensor_power": error}
    else:
        assert result["data"] == {"sensor_power": "sensor.power"}


@pytest.mark.asyncio
async def test_platform_setup_failure_closes_client():
    integration = import_module("custom_components.thessla_green")
    entry = MagicMock(entry_id="entry", data={"host": "gateway", "port": 502, "slave": 10})
    hass = SimpleNamespace(data={}, config_entries=SimpleNamespace(
        async_forward_entry_setups=AsyncMock(side_effect=RuntimeError("platform failed")),
    ))
    with patch.object(integration, "ThesslaGreenModbusController") as factory, \
            patch.object(integration, "ThesslaGreenCoordinator") as coordinator:
        factory.return_value.stop = AsyncMock()
        coordinator.return_value.async_config_entry_first_refresh = AsyncMock()
        with pytest.raises(RuntimeError, match="platform failed"):
            await integration.async_setup_entry(hass, entry)
        factory.return_value.stop.assert_awaited_once()
        assert "entry" not in hass.data[DOMAIN]
        entry.add_update_listener.assert_not_called()
