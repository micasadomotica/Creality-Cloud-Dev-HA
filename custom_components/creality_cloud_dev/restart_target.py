"""Resolve the supervised CC Tools app serving the configured URL."""

from __future__ import annotations

import asyncio
from ipaddress import ip_address, ip_interface
import socket
from typing import Any
from urllib.parse import urlparse


def endpoint(value: str) -> tuple[str, int] | None:
    """Only direct HTTP endpoints can be mapped to Supervisor port bindings."""
    try:
        url = urlparse(value)
        if (
            url.scheme != "http"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            return None
        return url.hostname.lower().rstrip("."), url.port or 80
    except ValueError:
        return None


def select_restart_app(
    url: str,
    apps: list[dict[str, Any]],
    host_addresses: set[str],
    resolved_addresses: set[str],
) -> dict[str, str] | None:
    """Prefer Supervisor's exact hostname, then require unique host/port routing."""
    if (parsed := endpoint(url)) is None:
        return None
    hostname, port = parsed
    apps = [app for app in apps
            if str(app.get("slug") or "").endswith("_cc_tools")
            and not app.get("host_network")
            and "8080/tcp" in (app.get("network") or {})]
    # Stopped apps can retain an IP subsequently assigned to another app. An
    # exact Supervisor hostname identifies the app independently of that IP.
    named = {
        str(app["slug"]): {"slug": str(app["slug"]), "name": str(app.get("name") or app["slug"])}
        for app in apps
        if hostname == str(app.get("hostname") or "").lower().rstrip(".")
    }
    if named:
        return next(iter(named.values())) if len(named) == 1 and port == 8080 else None
    matches = {}
    for app in apps:
        slug = str(app.get("slug") or "")
        bindings = app.get("network") or {}
        internal_ip = str(app.get("ip_address") or "")
        internal = bool(resolved_addresses) and resolved_addresses == {internal_ip}
        local = bool(resolved_addresses) and resolved_addresses <= host_addresses
        if (internal and port == 8080) or (
            local and bindings["8080/tcp"] == port
        ):
            matches[slug] = {"slug": slug, "name": str(app.get("name") or slug)}
    return next(iter(matches.values())) if len(matches) == 1 else None


async def async_resolve_restart_app(hass, url: str) -> dict[str, str] | None:
    """Read fresh Supervisor bindings before enabling or performing recovery."""
    parsed = endpoint(url)
    if parsed is None or "hassio" not in hass.config.components:
        return None

    # Optional: ordinary polling also works on installations without Supervisor.
    from homeassistant.components.hassio import get_supervisor_client

    async with asyncio.timeout(15):
        client = get_supervisor_client(hass)
        installed, network = await asyncio.gather(
            client.addons.list(), client.network.info()
        )
        apps = await asyncio.gather(
            *(
                client.addons.addon_info(app.slug)
                for app in installed
                if app.slug.endswith("_cc_tools")
            )
        )
        host_addresses = {
            str(ip_interface(str(address)).ip)
            for interface in network.interfaces
            if interface.enabled and interface.connected
            for config in (interface.ipv4, interface.ipv6)
            for address in config.address
        }
        hostname, port = parsed
        try:
            addresses = {str(ip_address(hostname))}
        except ValueError:
            results = await asyncio.get_running_loop().getaddrinfo(
                hostname, port, type=socket.SOCK_STREAM
            )
            addresses = {str(ip_address(result[4][0])) for result in results}
        return select_restart_app(
            url, [app.to_dict() for app in apps], host_addresses, addresses
        )
