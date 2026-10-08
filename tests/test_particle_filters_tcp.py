"""Exercise filter diagnostics and commands with a real pymodbus TCP client."""

import asyncio
import struct
from types import SimpleNamespace

import pytest

from custom_components.thessla_green.modbus_controller import ThesslaGreenModbusController
from custom_components.thessla_green.particle import particle_entities


@pytest.mark.asyncio
async def test_filter_control_messages_and_alarm_are_independent():
    known = (set(range(4)) | {16, 17, 33, 36, 41, 42, 43, 44, 48, 64, 65, 96, 97, 98,
                              4114, 4115, 4398, 4399, 4400, 8144, 8192, 8193, 12352}
             | set(range(50, 58)) | set(range(112, 122)) | set(range(1536, 1612)) | set(range(8128, 8135)))
    registers = {address: 0 for address in known}
    registers.update({16: 1, 33: 65526, 36: 35, 44: 0x0C1E, 96: 0x0100, 4398: 0x47,
                      8128: 0x1A2B, 8129: 0x3C4D, 8130: 0x5E6F, 8131: 0x0304, 8132: 2,
                      8193: 1})
    writes = []
    handlers = set()

    async def gateway(reader, writer):
        task = asyncio.current_task()
        handlers.add(task)
        try:
            while True:
                transaction, protocol, length, slave = struct.unpack(">HHHB", await reader.readexactly(7))
                function, address, value = struct.unpack(">BHH", await reader.readexactly(length - 1))
                assert slave == 30
                if function == 3:
                    assert value <= 16
                    if any(index not in known for index in range(address, address + value)):
                        payload = bytes([0x83, 2])
                    else:
                        payload = bytes([3, value * 2]) + b"".join(
                            struct.pack(">H", registers[index]) for index in range(address, address + value)
                        )
                elif function == 6:
                    writes.append((address, value))
                    registers[address] = value
                    if address == 42 and value == 3:
                        registers.update({41: 1, 4398: 0x43})
                    elif address == 4400 and value == 1:
                        registers[4398] = 0x31
                    payload = struct.pack(">BHH", 6, address, value)
                else:
                    payload = bytes([function | 0x80, 1])
                writer.write(struct.pack(">HHHB", transaction, protocol, len(payload) + 1, slave) + payload)
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(gateway, "127.0.0.1", 0)
    controller = ThesslaGreenModbusController("127.0.0.1", server.sockets[0].getsockname()[1], 30,
                                            device_type="particle")
    coordinator = SimpleNamespace(controller=controller, last_update_success=True)

    async def refresh():
        coordinator.safe_data = await controller.fetch_data()

    coordinator.async_request_refresh = refresh
    entry = SimpleNamespace(entry_id="particle", data={"device_type": "particle"})
    try:
        await refresh()
        assert writes == []
        buttons = {entity._key: entity for entity in particle_entities("button", coordinator, entry)}
        sensors = {entity._key: entity for entity in particle_entities("sensor", coordinator, entry)}
        binary = {entity._key: entity for entity in particle_entities("binary_sensor", coordinator, entry)}
        assert sensors["filter_message"].native_value == "Kontrola filtrów — błąd przepływu"
        assert binary["alarm_s116"].is_on
        await buttons["check_filters"].async_press()
        assert writes == [(42, 3)]
        assert sensors["filter_message_code"].native_value == 0x43
        assert not buttons["check_filters"].available
        registers.update({41: 0, 42: 0, 4398: 0x48})
        await refresh()
        assert sensors["filter_message"].native_value == "Procedura kontroli filtrów zakończona"
        assert binary["alarm_s116"].is_on
        await buttons["acknowledge_filter_message"].async_press()
        assert writes[-1] == (4398, 0)
        assert sensors["filter_message_code"].native_value == 0
        registers[4398] = 0x39
        await refresh()
        await buttons["accept_filter"].async_press()
        assert writes[-1] == (4400, 1)
        assert sensors["filter_message_code"].native_value == 0x31
        assert registers[96] == 0x0100
    finally:
        await controller.stop()
        server.close()
        await server.wait_closed()
        if handlers:
            await asyncio.gather(*handlers)
