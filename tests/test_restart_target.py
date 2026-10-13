"""Restart routing for local, upstream, ambiguous and remote installations."""

import asyncio
import importlib.util
from ipaddress import IPv4Interface, IPv6Interface
from pathlib import Path
import socket
import sys
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import AsyncMock, patch


SPEC = importlib.util.spec_from_file_location(
    "restart_target",
    Path(__file__).parents[1] / "custom_components/creality_cloud/restart_target.py",
)
target = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(target)
HOST = "192.168.1.44"


def app(slug, port, ip):
    return {
        "slug": slug, "name": slug, "hostname": slug.replace("_", "-"),
        "ip_address": ip, "host_network": False, "network": {"8080/tcp": port},
    }


UPSTREAM = app("8966b8c7_cc_tools", 8080, "172.30.33.1")
DEV = app("local_cc_tools", 8088, "172.30.33.2")


class RestartTargetTests(unittest.TestCase):
    def select(self, url, apps=None, addresses=None):
        return target.select_restart_app(
            url, [UPSTREAM, DEV] if apps is None else apps,
            {HOST, "fd00::44"}, {HOST} if addresses is None else addresses,
        )

    def test_dev_and_upstream_coexist(self):
        self.assertEqual(self.select(f"http://{HOST}:8088")["slug"], "local_cc_tools")
        self.assertEqual(self.select(f"http://{HOST}:8080")["slug"], UPSTREAM["slug"])

    def test_actual_mapping_instead_of_magic_dev_port(self):
        changed = {**DEV, "network": {"8080/tcp": 9001}}
        self.assertEqual(self.select(f"http://{HOST}:9001", [changed])["slug"], DEV["slug"])
        self.assertIsNone(self.select(f"http://{HOST}:8088", [changed]))

    def test_internal_hostname_uses_internal_port(self):
        result = self.select("http://local-cc-tools:8080", addresses={DEV["ip_address"]})
        self.assertEqual(result["slug"], DEV["slug"])
        self.assertIsNone(self.select("http://local-cc-tools:8088", addresses={DEV["ip_address"]}))

    def test_internal_address_and_alias(self):
        for host in (DEV["ip_address"], "dev.internal"):
            with self.subTest(host=host):
                result = self.select(f"http://{host}:8080", addresses={DEV["ip_address"]})
                self.assertEqual(result["slug"], DEV["slug"])

    def test_local_hostname_and_ipv6(self):
        self.assertEqual(self.select("http://homeassistant.local:8088/")["slug"], DEV["slug"])
        self.assertEqual(self.select("http://[fd00::44]:8088", addresses={"fd00::44"})["slug"], DEV["slug"])

    def test_remote_host_with_same_port_never_restarts_local_dev(self):
        self.assertIsNone(self.select("http://192.168.1.99:8088", addresses={"192.168.1.99"}))
        self.assertIsNone(self.select("http://mixed.example:8088", addresses={HOST, "192.168.1.99"}))

    def test_no_fallback_when_dev_missing_or_binding_disabled(self):
        self.assertIsNone(self.select(f"http://{HOST}:8088", [UPSTREAM]))
        self.assertIsNone(self.select(f"http://{HOST}:8088", [{**DEV, "network": {"8080/tcp": None}}]))

    def test_ambiguous_or_host_network_targets_are_rejected(self):
        twin = app("other_cc_tools", 8088, "172.30.33.3")
        self.assertIsNone(self.select(f"http://{HOST}:8088", [DEV, twin]))
        self.assertIsNone(self.select(f"http://{HOST}:8088", [{**DEV, "host_network": True}]))

    def test_proxy_invalid_and_credential_urls_do_not_match(self):
        for url in (
            f"https://{HOST}:8088", f"http://{HOST}:8088/dev", f"http://{HOST}:8088?q=x",
            f"http://{HOST}:8088#x", f"http://user:pass@{HOST}:8088", "http://[broken",
            f"http://{HOST}:99999", "", "not-a-url",
        ):
            with self.subTest(url=url):
                self.assertIsNone(self.select(url))


class SupervisorDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_bindings_and_supervisor_host_addresses(self):
        interface = SimpleNamespace(
            enabled=True, connected=True,
            ipv4=SimpleNamespace(address=[IPv4Interface(HOST + "/24")]),
            ipv6=SimpleNamespace(address=[IPv6Interface("fd00::44/64")]),
        )
        client = SimpleNamespace(
            addons=SimpleNamespace(
                list=AsyncMock(return_value=[SimpleNamespace(slug=DEV["slug"])]),
                addon_info=AsyncMock(return_value=SimpleNamespace(to_dict=lambda: DEV)),
            ),
            network=SimpleNamespace(info=AsyncMock(return_value=SimpleNamespace(interfaces=[interface]))),
        )
        module = ModuleType("homeassistant.components.hassio")
        module.get_supervisor_client = lambda hass: client
        hass = SimpleNamespace(config=SimpleNamespace(components={"hassio"}))
        with patch.dict(sys.modules, {"homeassistant.components.hassio": module}):
            result = await target.async_resolve_restart_app(hass, f"http://{HOST}:8088")
            self.assertEqual(result["slug"], DEV["slug"])
            client.addons.addon_info.assert_awaited_once_with("local_cc_tools")
            with patch.object(asyncio.get_running_loop(), "getaddrinfo", AsyncMock(return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (HOST, 8088))
            ])):
                result = await target.async_resolve_restart_app(hass, "http://homeassistant.local:8088")
                self.assertEqual(result["slug"], DEV["slug"])

    async def test_without_supervisor_is_supported_for_polling_only(self):
        hass = SimpleNamespace(config=SimpleNamespace(components=set()))
        self.assertIsNone(await target.async_resolve_restart_app(hass, f"http://{HOST}:8088"))


if __name__ == "__main__":
    unittest.main()
