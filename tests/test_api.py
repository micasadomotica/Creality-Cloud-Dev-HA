"""Exercise HTTP methods, payloads and error translation without a live server."""

import ast
from types import SimpleNamespace
import unittest
from urllib.parse import urljoin

from test_session_and_devices import ROOT, load_objects


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self, **kwargs):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        names = {node.name for node in ast.parse((ROOT / "api.py").read_text(encoding="utf-8")).body if isinstance(node, ast.ClassDef)}
        self.namespace = load_objects("api.py", names, {
            "urljoin": urljoin, "ClientTimeout": SimpleNamespace, "ClientError": ConnectionError,
        })
        self.calls = []
        self.response = Response({"ok": True, "apiVersion": 1, "accountId": "42", "models": {"uploadsToday": 1}})

        def request(method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            return self.response

        self.api = self.namespace["CrealityCloudApi"](SimpleNamespace(request=request), "http://ha:8088")

    async def test_models_route_and_toggle_preserve_other_schedule_fields(self):
        self.assertEqual((await self.api.async_models())["models"]["uploadsToday"], 1)
        self.assertEqual(self.calls[0][:2], ("GET", "http://ha:8088/api/integration/models"))
        await self.api.async_set_models_enabled(False)
        self.assertEqual(self.calls[1][:2], ("PATCH", "http://ha:8088/api/integration/models"))
        self.assertEqual(self.calls[1][2]["json"], {"enabled": False})

    async def test_unavailable_old_api_invalid_json_and_rejected_schedule_are_api_errors(self):
        for payload, status in [(ValueError("HTML not JSON"), 404), ([], 200),
                                ({"ok": True, "apiVersion": "invalid"}, 200),
                                ({"ok": False, "message": "Configure schedule first"}, 409)]:
            with self.subTest(payload=payload):
                self.response = Response(payload, status)
                with self.assertRaises(self.namespace["CrealityCloudApiError"]):
                    await self.api.async_models()
