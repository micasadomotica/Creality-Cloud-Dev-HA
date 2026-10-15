"""Exercise the production flow with isolated Home Assistant interfaces."""

import __future__
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from urllib.parse import urlparse

ROOT = Path(__file__).parents[1] / "custom_components/creality_cloud_dev"


class Abort(Exception):
    pass


class ConfigFlow:
    def __init_subclass__(cls, domain):
        cls.domain = domain

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self, **kwargs):
        assert not kwargs, "Adding a hub must never change an existing URL"
        if (self.domain, self.unique_id) in self.entries:
            raise Abort("already_configured")

    def async_create_entry(self, **kwargs):
        entry = SimpleNamespace(unique_id=self.unique_id, **kwargs)
        self.entries[self.domain, self.unique_id] = entry
        return {"type": "create_entry", **kwargs}

    def _get_reconfigure_entry(self):
        return self.entry

    def _abort_if_unique_id_mismatch(self):
        if self.unique_id != self.entry.unique_id:
            raise Abort("unique_id_mismatch")

    def async_update_reload_and_abort(self, entry, data_updates):
        entry.data.update(data_updates)
        self.reloaded = entry
        return {"type": "abort", "reason": "reconfigure_successful"}


def load_flow(probe):
    tree = ast.parse((ROOT / "config_flow.py").read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
    const_tree = ast.parse((ROOT / "const.py").read_text(encoding="utf-8"))
    domain = next(ast.literal_eval(node.value) for node in const_tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "DOMAIN" for target in node.targets))
    namespace = {"config_entries": SimpleNamespace(ConfigFlow=ConfigFlow), "DOMAIN": domain, "CONF_URL": "url",
                 "vol": SimpleNamespace(Schema=lambda schema: schema, Required=lambda key, **_: key),
                 "async_probe_url": probe, "CrealityCloudApiError": ConnectionError, "urlparse": urlparse}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "config_flow.py", "exec",
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.probe = AsyncMock(return_value={"account": {"userId": "42", "name": "MiCasaDomotica"}})
        self.namespace = load_flow(self.probe)
        self.flow = self.namespace["CrealityCloudConfigFlow"]()
        self.flow.hass = object()
        self.original = SimpleNamespace(unique_id="42", data={"url": "http://ha:8080"})
        self.flow.entries = {("creality_cloud", "42"): self.original}

    async def test_always_asks_url_without_detecting_original_app(self):
        result = await self.flow.async_step_user()
        self.assertEqual(result["step_id"], "user")
        self.assertIn("url", result["data_schema"])
        self.probe.assert_not_awaited()

    async def test_same_account_creates_separate_dev_hub(self):
        result = await self.flow.async_step_user({"url": "http://ha:8088/"})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "MiCasaDomotica · Dev")
        self.assertEqual(result["data"]["url"], "http://ha:8088")
        self.assertEqual(len(self.flow.entries), 2)
        self.assertIn(("creality_cloud_dev", "42"), self.flow.entries)
        self.assertEqual(self.original.data["url"], "http://ha:8080")

    async def test_second_dev_add_never_retargets_existing_hub(self):
        await self.flow.async_step_user({"url": "http://ha:8088"})
        with self.assertRaisesRegex(Abort, "already_configured"):
            await self.flow.async_step_user({"url": "http://ha:8080"})
        self.assertEqual(self.flow.entries["creality_cloud_dev", "42"].data["url"], "http://ha:8088")
        self.assertEqual(len(self.flow.entries), 2)

    async def test_explicit_reconfigure_reloads_same_entry_only(self):
        await self.flow.async_step_user({"url": "http://ha:8088"})
        self.flow.entry = self.flow.entries["creality_cloud_dev", "42"]
        self.assertEqual((await self.flow.async_step_reconfigure())["step_id"], "reconfigure")
        result = await self.flow.async_step_reconfigure({"url": "http://ha:8099"})
        self.assertEqual(result["reason"], "reconfigure_successful")
        self.assertIs(self.flow.reloaded, self.flow.entry)
        self.assertEqual(self.flow.entry.data["url"], "http://ha:8099")
        self.assertEqual(self.original.data["url"], "http://ha:8080")
        self.assertEqual(len(self.flow.entries), 2)

    async def test_reconfigure_rejects_another_account(self):
        self.flow.entry = SimpleNamespace(unique_id="other", data={"url": "http://ha:8088"})
        with self.assertRaisesRegex(Abort, "unique_id_mismatch"):
            await self.flow.async_step_reconfigure({"url": "http://ha:8099"})
        self.assertEqual(self.flow.entry.data["url"], "http://ha:8088")

    async def test_invalid_or_unreachable_endpoint_does_not_add_entry(self):
        for url in ("ha:8088", "http://ha:bad", "http://ha:99999", "http://[bad", "http://ha:0", "http://u:p@ha:8088"):
            result = await self.flow.async_step_user({"url": url})
            self.assertEqual(result["errors"], {"url": "invalid_url"})
        self.probe.assert_not_awaited()
        self.probe.side_effect = ConnectionError()
        result = await self.flow.async_step_user({"url": "http://ha:8088"})
        self.assertEqual(result["errors"], {"base": "cannot_connect"})
        self.assertEqual(len(self.flow.entries), 1)

    async def test_account_must_be_known_before_creating_hub(self):
        self.probe.return_value = {"account": {}}
        result = await self.flow.async_step_user({"url": "http://ha:8088"})
        self.assertEqual(result["errors"], {"base": "account_unavailable"})
        self.assertEqual(len(self.flow.entries), 1)
