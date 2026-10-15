"""Config flow for Creality Cloud."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CrealityCloudApi, CrealityCloudApiError
from .const import CONF_URL, DOMAIN


async def async_probe_url(hass: HomeAssistant, url: str) -> dict[str, Any]:
    """Validate one CC Tools endpoint."""
    return await CrealityCloudApi(
        async_get_clientsession(hass), url, request_timeout=5
    ).async_status()


class CrealityCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Creality Cloud config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._url = ""
        self._state: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Always let the user choose the Dev endpoint."""
        if user_input is not None:
            return await self._async_validate_url(str(user_input[CONF_URL]))

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_URL): str}),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the endpoint explicitly without creating another account."""
        if user_input is not None:
            return await self._async_validate_url(str(user_input[CONF_URL]), "reconfigure")
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_URL, default=self._get_reconfigure_entry().data[CONF_URL]): str}),
        )

    async def _async_validate_url(self, value: str, step_id: str = "user") -> ConfigFlowResult:
        url = normalize_url(value)
        if not url:
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema({vol.Required(CONF_URL, default=value): str}),
                errors={CONF_URL: "invalid_url"},
            )
        try:
            state = await async_probe_url(self.hass, url)
        except CrealityCloudApiError:
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema({vol.Required(CONF_URL, default=url): str}),
                errors={"base": "cannot_connect"},
            )
        account_id = str(state.get("account", {}).get("userId") or "").strip()
        if not account_id:
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema({vol.Required(CONF_URL, default=url): str}),
                errors={"base": "account_unavailable"},
            )
        await self.async_set_unique_id(account_id)
        if step_id == "reconfigure":
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data_updates={CONF_URL: url}
            )
        self._url = url
        self._state = state
        return await self._async_create_entry()

    async def _async_create_entry(self) -> ConfigFlowResult:
        account = self._state.get("account", {})
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=str(account.get("name") or "Creality Cloud") + " · Dev",
            data={CONF_URL: self._url},
        )


def normalize_url(value: str) -> str:
    """Return a normalized HTTP URL or an empty string."""
    raw = str(value or "").strip().rstrip("/")
    try:
        parsed = urlparse(raw)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or any(char.isspace() for char in raw)):
            return ""
        port = parsed.port
        if port == 0:
            return ""
    except ValueError:
        return ""
    return raw
