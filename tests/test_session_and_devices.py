"""Verify upstream session data and device links without a live HA instance."""

import __future__
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).parents[1] / "custom_components/creality_cloud_dev"


def load_objects(filename, names, namespace):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if getattr(node, "name", None) in names
             or isinstance(node, ast.Assign) and any(
                 isinstance(target, ast.Name) and target.id in names for target in node.targets)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec",
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace


class SessionTests(unittest.TestCase):
    def setUp(self):
        namespace = load_objects("sensor.py", {"ACCOUNT_SENSORS", "session_attributes"}, {
            "CrealityCloudSensorDescription": SimpleNamespace,
            "SensorDeviceClass": SimpleNamespace(ENUM="enum"),
            "SensorStateClass": SimpleNamespace(TOTAL="total"),
        })
        self.sensor = next(item for item in namespace["ACCOUNT_SENSORS"] if item.key == "session")

    def test_session_states_and_diagnostics_exclude_private_data(self):
        self.assertEqual(self.sensor.options, ["open", "closed"])
        for state in self.sensor.options:
            data = {"session": {"state": state, "checkedAt": "2026-10-15T12:00:00Z",
                                "reason": "expired" if state == "closed" else "",
                                "token": "must-not-be-exposed"}}
            self.assertEqual(self.sensor.value_fn(data), state)
            self.assertEqual(self.sensor.attributes_fn(data), {
                "checked_at": "2026-10-15T12:00:00Z",
                "reason": "expired" if state == "closed" else None,
            })

    def test_missing_session_is_closed_without_diagnostics(self):
        self.assertEqual(self.sensor.value_fn({}), "closed")
        self.assertEqual(self.sensor.attributes_fn({}), {"checked_at": None, "reason": None})


class DeviceTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_is_registered_before_platforms_and_url_listener_survives(self):
        entry = SimpleNamespace(entry_id="existing", title="Account · Dev", data={"url": "http://ha:8088"},
                                async_on_unload=Mock(), add_update_listener=Mock(return_value="unsubscribe"))
        coordinator = SimpleNamespace(data={"account": {"name": "Account"}}, async_config_entry_first_refresh=AsyncMock())
        devices = SimpleNamespace(async_get_or_create=Mock(return_value=SimpleNamespace(id="account-device")))
        entities = SimpleNamespace(async_get_entity_id=Mock(return_value=None))

        async def forward(config_entry, platforms):
            self.assertEqual(config_entry.runtime_data.account_device_id, "account-device")
            devices.async_get_or_create.assert_called_once()

        hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock(side_effect=forward)))
        listener = AsyncMock()
        namespace = load_objects("__init__.py", {"async_setup_entry"}, {
            "CrealityCloudApi": Mock(return_value="api"), "async_get_clientsession": Mock(),
            "CrealityCloudCoordinator": Mock(return_value=coordinator), "CONF_URL": "url", "DOMAIN": "creality_cloud_dev",
            "dr": SimpleNamespace(async_get=lambda _: devices),
            "er": SimpleNamespace(async_get=lambda _: entities, async_entries_for_config_entry=lambda *_: []),
            "CrealityCloudRuntimeData": lambda api, cc, device_id: SimpleNamespace(api=api, coordinator=cc, account_device_id=device_id),
            "async_entry_updated": listener, "REMOVED_ENTITY_UNIQUE_ID_SUFFIXES": (), "PLATFORMS": ["sensor", "switch"],
        })
        self.assertTrue(await namespace["async_setup_entry"](hass, entry))
        self.assertEqual(devices.async_get_or_create.call_args.kwargs["identifiers"], {("creality_cloud_dev", "account:existing")})
        entry.add_update_listener.assert_called_once_with(listener)
        entry.async_on_unload.assert_called_once_with("unsubscribe")
        hass.config_entries.async_forward_entry_setups.assert_awaited_once()

    async def test_printer_keeps_identifiers_and_links_to_registered_account(self):
        class CoordinatorEntity:
            def __class_getitem__(cls, _):
                return cls

            def __init__(self, coordinator):
                self.coordinator = coordinator

        namespace = load_objects("entity.py", {"CrealityCloudEntity", "CrealityCloudPrinterEntity"}, {
            "CoordinatorEntity": CoordinatorEntity, "CrealityCloudCoordinator": object,
            "DeviceInfo": dict, "DOMAIN": "creality_cloud_dev",
        })
        entry = SimpleNamespace(entry_id="existing", title="Account · Dev", data={"url": "http://ha:8088"},
                                runtime_data=SimpleNamespace(account_device_id="account-device",
                                    coordinator=SimpleNamespace(data={"printers": [{"id": "p1", "name": "Printer"}]})))
        entity = namespace["CrealityCloudPrinterEntity"](entry, "p1", "status")
        self.assertEqual(entity._attr_unique_id, "existing_printer_p1_status")
        self.assertEqual(entity.device_info["identifiers"], {("creality_cloud_dev", "existing:printer:p1")})
        self.assertEqual(entity.device_info["via_device_id"], "account-device")
        self.assertNotIn("via_device", entity.device_info)
