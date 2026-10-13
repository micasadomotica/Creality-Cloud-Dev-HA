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
    """Require one app matching the host AND actual port, never the port alone."""
    if (parsed := endpoint(url)) is None:
        return None
    hostname, port = parsed
    matches = {}
    for app in apps:
        slug = str(app.get("slug") or "")
        if not slug.endswith("_cc_tools") or app.get("host_network"):
            continue
        bindings = app.get("network") or {}
        if "8080/tcp" not in bindings:
            continue
        internal_host = str(app.get("hostname") or "").lower().rstrip(".")
        internal_ip = str(app.get("ip_address") or "")
        internal = hostname == internal_host or (
            bool(resolved_addresses) and resolved_addresses == {internal_ip}
        )
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
