"""Exercise the actual coordinator with lightweight Home Assistant interfaces."""

from datetime import UTC, datetime, timedelta
import importlib.util
import ast
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch


ROOT = Path(__file__).parents[1] / "custom_components/creality_cloud"
PKG = "_cc_restart_tests"


def load_coordinator():
    modules = {}
    for name in (
        PKG, f"{PKG}.api", "homeassistant", "homeassistant.config_entries",
        "homeassistant.const", "homeassistant.core", "homeassistant.exceptions",
        "homeassistant.helpers", "homeassistant.helpers.update_coordinator",
        "homeassistant.helpers.storage",
    ):
        modules[name] = ModuleType(name)
    modules[PKG].__path__ = [str(ROOT)]
    modules[f"{PKG}.api"].CrealityCloudApi = object
    modules[f"{PKG}.api"].CrealityCloudApiError = type("ApiError", (Exception,), {})
    modules["homeassistant.const"].Platform = SimpleNamespace(SENSOR="sensor", SWITCH="switch")
    modules["homeassistant.config_entries"].ConfigEntry = object
    modules["homeassistant.core"].HomeAssistant = object

    class HomeAssistantError(Exception):
        def __init__(self, **kwargs):
            super().__init__(kwargs)

    class Coordinator:
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass, *args, **kwargs):
            self.hass = hass

        def async_update_listeners(self):
            pass

    class Store:
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, *args):
            self.async_save = AsyncMock()
            self.async_load = AsyncMock(return_value={})

    modules["homeassistant.exceptions"].HomeAssistantError = HomeAssistantError
    modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = Coordinator
    modules["homeassistant.helpers.update_coordinator"].UpdateFailed = RuntimeError
    modules["homeassistant.helpers.storage"].Store = Store
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location(f"{PKG}.coordinator", ROOT / "coordinator.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


coordinator = load_coordinator()
NOW = datetime.now(UTC)
DEV = {"slug": "local_cc_tools", "name": "CC Tools Dev"}
UPSTREAM = {"slug": "8966b8c7_cc_tools", "name": "CC Tools"}


class RestartCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.new_coordinator()
        self.patcher = patch.object(coordinator, "async_resolve_restart_app", self.resolve)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def new_coordinator(self):
        self.entry = SimpleNamespace(
            entry_id="test", data={"url": "http://192.168.1.44:8088"},
            options={"auto_restart": True},
        )
        def update(entry, **kwargs):
            entry.options = kwargs.get("options", entry.options)
        self.hass = SimpleNamespace(
            services=SimpleNamespace(has_service=Mock(return_value=True), async_call=AsyncMock()),
            config_entries=SimpleNamespace(async_update_entry=Mock(side_effect=update)),
        )
        api = SimpleNamespace(base_url=self.entry.data["url"])
        self.cc = coordinator.CrealityCloudCoordinator(self.hass, self.entry, api)
        if hasattr(self, "resolve"):
            self.resolve.reset_mock(return_value=True, side_effect=True)
            self.resolve.return_value = DEV
        else:
            self.resolve = AsyncMock(return_value=DEV)

    async def test_restarts_dev_and_records_recovery(self):
        await self.cc._async_restart_if_allowed("stale", NOW)
        self.hass.services.async_call.assert_awaited_once_with(
            "hassio", "app_restart", {"app": "local_cc_tools"}, blocking=True
        )
        self.assertEqual(self.cc._restart_timestamps, [NOW])
        self.assertEqual(self.cc.watchdog_attributes["restart_app"], "local_cc_tools")
        self.assertEqual(self.cc._watchdog_status, "stabilizing")

    async def test_resolves_fresh_target_for_each_attempt(self):
        self.resolve.return_value = UPSTREAM
        self.cc.api.base_url = self.entry.data["url"] = "http://192.168.1.44:8080"
        await self.cc._async_restart_if_allowed("stale", NOW)
        self.assertEqual(self.hass.services.async_call.await_args.args[2], {"app": UPSTREAM["slug"]})

    async def test_unresolved_target_does_not_restart_or_count_success(self):
        self.resolve.return_value = None
        await self.cc._async_restart_if_allowed("stale", NOW)
        self.hass.services.async_call.assert_not_awaited()
        self.assertEqual(self.cc._restart_timestamps, [])
        self.assertEqual(self.cc._watchdog_status, "restart_target_unresolved")
        self.assertFalse(self.cc._restart_in_progress)

    async def test_supervisor_failure_does_not_restart(self):
        self.resolve.side_effect = TimeoutError
        with self.assertLogs(coordinator.__name__, level="ERROR"):
            await self.cc._async_restart_if_allowed("stale", NOW)
        self.hass.services.async_call.assert_not_awaited()
        self.assertEqual(self.cc._watchdog_status, "restart_target_unresolved")

    async def test_url_changed_before_reloading_never_restarts_old_target(self):
        self.entry.data["url"] = "http://192.168.1.44:8080"
        await self.cc._async_restart_if_allowed("stale", NOW)
        self.resolve.assert_not_awaited()
        self.hass.services.async_call.assert_not_awaited()

    async def test_url_or_switch_change_during_lookup_cancels_restart(self):
        for change in ("url", "switch"):
            with self.subTest(change=change):
                self.new_coordinator()
                async def changed(*args):
                    if change == "url":
                        self.entry.data["url"] = "http://192.168.1.44:8080"
                    else:
                        self.entry.options["auto_restart"] = False
                    return DEV
                self.resolve.side_effect = changed
                await self.cc._async_restart_if_allowed("stale", NOW)
                self.hass.services.async_call.assert_not_awaited()

    async def test_cooldown_daily_limit_and_missing_service_are_preserved(self):
        for guard in ("cooldown", "daily_limit", "service", "busy"):
            with self.subTest(guard=guard):
                self.new_coordinator()
                if guard == "cooldown":
                    self.cc._restart_timestamps = [NOW - timedelta(hours=1)]
                elif guard == "daily_limit":
                    self.cc._restart_timestamps = [NOW - timedelta(hours=n) for n in (9, 6, 3)]
                elif guard == "service":
                    self.hass.services.has_service.return_value = False
                else:
                    self.cc._restart_in_progress = True
                await self.cc._async_restart_if_allowed("stale", NOW)
                self.resolve.assert_not_awaited()
                self.hass.services.async_call.assert_not_awaited()

    async def test_service_error_is_not_recorded_as_success(self):
        self.hass.services.async_call.side_effect = RuntimeError("failed")
        with self.assertLogs(coordinator.__name__, level="ERROR"):
            await self.cc._async_restart_if_allowed("stale", NOW)
        self.assertEqual(self.cc._restart_timestamps, [])
        self.assertEqual(self.cc._watchdog_status, "restart_failed")
        self.assertFalse(self.cc._restart_in_progress)

    async def test_enabling_requires_resolved_target_but_disabling_does_not(self):
        self.resolve.return_value = None
        self.entry.options["auto_restart"] = False
        with self.assertRaises(coordinator.HomeAssistantError):
            await self.cc.async_set_auto_restart_enabled(True)
        self.assertFalse(self.entry.options["auto_restart"])
        self.resolve.reset_mock()
        await self.cc.async_set_auto_restart_enabled(False)
        self.resolve.assert_not_awaited()

    async def test_enabling_valid_dev_exposes_selected_target(self):
        self.entry.options["auto_restart"] = False
        await self.cc.async_set_auto_restart_enabled(True)
        self.assertTrue(self.entry.options["auto_restart"])
        self.assertEqual(self.cc.watchdog_attributes["restart_app"], "local_cc_tools")

    async def test_two_missed_slots_reach_the_correct_restart_service(self):
        await self.cc._async_consider_auto_restart({
            "scheduler": {"running": False},
            "schedule": {"pending": [
                {"task": "checkin", "plannedAt": (NOW - timedelta(minutes=30)).isoformat()},
                {"task": "downloads", "plannedAt": (NOW - timedelta(minutes=15)).isoformat()},
            ]},
        })
        self.assertEqual(self.hass.services.async_call.await_args.args[2], {"app": "local_cc_tools"})


class UrlReloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_url_changes_reload_the_existing_entry(self):
        # Compile the production callback without importing platform setup code.
        tree = ast.parse((ROOT / "__init__.py").read_text(encoding="utf-8"))
        callback = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                        and node.name == "async_entry_updated")
        for arg in callback.args.args:
            arg.annotation = None
        callback.returns = None
        namespace = {"CONF_URL": "url"}
        exec(compile(ast.Module(body=[callback], type_ignores=[]), "__init__.py", "exec"), namespace)
        hass = SimpleNamespace(config_entries=SimpleNamespace(async_reload=AsyncMock()))
        entry = SimpleNamespace(
            entry_id="same-account", data={"url": "http://ha:8080"},
            runtime_data=SimpleNamespace(api=SimpleNamespace(base_url="http://ha:8080")),
        )
        await namespace["async_entry_updated"](hass, entry)
        hass.config_entries.async_reload.assert_not_awaited()
        entry.data["url"] = "http://ha:8088"
        await namespace["async_entry_updated"](hass, entry)
        hass.config_entries.async_reload.assert_awaited_once_with("same-account")


if __name__ == "__main__":
    unittest.main()
