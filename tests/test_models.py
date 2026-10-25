"""Verify Models entities, schedule controls and API failure isolation."""

from datetime import UTC, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from test_session_and_devices import load_objects
from test_restart_coordinator import coordinator


class CoordinatorEntity:
    def __class_getitem__(cls, _):
        return cls

    def __init__(self, value):
        self.coordinator = value

    @property
    def available(self):
        return self.coordinator.last_update_success


class ModelsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.namespace = load_objects("entity.py", {"CrealityCloudEntity", "CrealityCloudModelsEntity"}, {
            "CoordinatorEntity": CoordinatorEntity, "CrealityCloudCoordinator": object,
            "DeviceInfo": dict, "DOMAIN": "creality_cloud_dev",
        })
        self.sensors = load_objects("sensor.py", {"CrealityCloudModelsSensor", "parse_datetime", "MODELS_SENSOR_KEYS"}, {
            **self.namespace, "SensorEntity": type("SensorEntity", (), {}),
            "SensorDeviceClass": SimpleNamespace(TIMESTAMP="timestamp"), "datetime": datetime,
        })
        self.switches = load_objects("switch.py", {"CrealityCloudModelsScheduleSwitch"}, {
            **self.namespace, "SwitchEntity": type("SwitchEntity", (), {}),
            "SwitchEntityDescription": SimpleNamespace, "CrealityCloudApiError": ConnectionError,
            "HomeAssistantError": RuntimeError,
        })
        self.models = {
            "defaultCategory": {"category": "Impresoras 3D", "subcategory": "Otro"},
            "availableCount": 7, "lastModel": {"name": "Diseño último", "id": "42", "url": "https://example.com/42"},
            "lastUploadAt": "2026-10-25T08:00:00Z", "nextUploadAt": "2026-10-26T08:00:00Z",
            "uploadsToday": 2, "enabled": True, "dailyLimit": 5, "timezone": "Europe/Madrid",
        }
        self.cc = SimpleNamespace(data={"models": self.models}, last_update_success=True,
                                  async_set_models_enabled=AsyncMock())
        self.entry = SimpleNamespace(entry_id="existing", data={"url": "http://ha:8088"},
            runtime_data=SimpleNamespace(coordinator=self.cc, account_device_id="account-device"))

    def sensor(self, key):
        return self.sensors["CrealityCloudModelsSensor"](self.entry, key)

    def test_six_values_and_separate_device_linked_to_existing_account(self):
        values = {key: self.sensor(key).native_value for key in self.sensors["MODELS_SENSOR_KEYS"]}
        self.assertEqual(values, {
            "default_category": "Impresoras 3D / Otro", "available": 7,
            "last_model_upload": "Diseño último", "last_upload": datetime(2026, 10, 25, 8, tzinfo=UTC),
            "next_upload": datetime(2026, 10, 26, 8, tzinfo=UTC), "uploads_today": 2,
        })
        entity = self.sensor("available")
        self.assertEqual(entity._attr_unique_id, "existing_models_available")
        self.assertEqual(entity.device_info["identifiers"], {("creality_cloud_dev", "existing:models")})
        self.assertEqual(entity.device_info["via_device_id"], "account-device")
        self.assertEqual(entity.device_info["model"], "Creality Cloud Models")

    def test_unknown_timestamps_offline_models_and_zero_are_distinct(self):
        self.models.update(lastUploadAt="bad", nextUploadAt="2026-10-25T08:00:00", uploadsToday=0)
        self.assertIsNone(self.sensor("last_upload").native_value)
        self.assertIsNone(self.sensor("next_upload").native_value)
        self.assertEqual(self.sensor("uploads_today").native_value, 0)
        self.models.update(enabled=False, nextUploadAt="2026-10-25T08:00:00Z")
        self.assertIsNone(self.sensor("next_upload").native_value)
        self.assertTrue(self.sensor("uploads_today").available)
        self.cc.data["models"] = None
        self.assertFalse(self.sensor("uploads_today").available)
        self.assertIsNone(self.sensor("uploads_today").native_value)

    def test_long_model_name_keeps_full_name_in_attributes(self):
        self.models["lastModel"]["name"] = "á" * 300
        entity = self.sensor("last_model_upload")
        self.assertEqual(len(entity.native_value), 255)
        self.assertEqual(len(entity.extra_state_attributes["name"]), 300)

    async def test_switch_calls_toggle_not_schedule_replacement_and_reports_errors(self):
        switch = self.switches["CrealityCloudModelsScheduleSwitch"](self.entry)
        self.assertEqual(switch.device_info, self.sensor("available").device_info)
        self.assertTrue(switch.is_on)
        await switch.async_turn_off()
        self.cc.async_set_models_enabled.assert_awaited_once_with(False)
        await switch.async_turn_on()
        self.cc.async_set_models_enabled.assert_awaited_with(True)
        self.cc.async_set_models_enabled.side_effect = ConnectionError("Configure schedule first")
        with self.assertRaisesRegex(RuntimeError, "Configure schedule first"):
            await switch.async_turn_on()


class ModelsCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_models_failure_or_wrong_account_preserves_account_and_printers(self):
        for models in (coordinator.CrealityCloudApiError("HTTP 404"), {"accountId": "other", "models": {}},
                       {"accountId": "42", "models": {"uploadsToday": 3}}):
            with self.subTest(models=models):
                api = SimpleNamespace(async_status=AsyncMock(return_value={"account": {"userId": "42"}, "printers": [{"id": "p1"}]}),
                                      async_events=AsyncMock(return_value=[]), async_models=AsyncMock())
                if isinstance(models, Exception):
                    api.async_models.side_effect = models
                else:
                    api.async_models.return_value = models
                entry = SimpleNamespace(entry_id="test", options={})
                cc = coordinator.CrealityCloudCoordinator(SimpleNamespace(), entry, api)
                state = await cc._async_update_data()
                self.assertEqual(state["account"]["userId"], "42")
                self.assertEqual(state["printers"], [{"id": "p1"}])
                self.assertEqual(state["models"], {"uploadsToday": 3} if isinstance(models, dict) and models["accountId"] == "42" else None)

    async def test_toggle_refreshes_after_success_and_preserves_error(self):
        api = SimpleNamespace(async_set_models_enabled=AsyncMock())
        cc = coordinator.CrealityCloudCoordinator(SimpleNamespace(), SimpleNamespace(entry_id="test"), api)
        cc.async_request_refresh = AsyncMock()
        await cc.async_set_models_enabled(False)
        api.async_set_models_enabled.assert_awaited_once_with(False)
        cc.async_request_refresh.assert_awaited_once()
        cc.async_request_refresh.reset_mock()
        api.async_set_models_enabled.side_effect = coordinator.CrealityCloudApiError("Invalid schedule")
        with self.assertRaises(coordinator.CrealityCloudApiError):
            await cc.async_set_models_enabled(True)
        cc.async_request_refresh.assert_not_awaited()
