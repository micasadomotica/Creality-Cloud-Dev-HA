"""Entity helpers for Creality Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CrealityCloudConfigEntry
from .const import DOMAIN
from .coordinator import CrealityCloudCoordinator


class CrealityCloudEntity(CoordinatorEntity[CrealityCloudCoordinator]):
    """Base entity attached to the Creality Cloud account device."""

    _attr_has_entity_name = True

    def __init__(self, entry: CrealityCloudConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data.coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the account device."""
        account = self.coordinator.data.get("account", {})
        return DeviceInfo(
            identifiers={(DOMAIN, f"account:{self.entry.entry_id}")},
            manufacturer="Creality Cloud",
            model="CC Tools Dev account",
            name=str(account.get("name") or "Creality Cloud") + " · Dev",
            configuration_url=self.entry.data.get("url"),
        )


class CrealityCloudModelsEntity(CrealityCloudEntity):
    """Base entity for the separate model library device."""

    def __init__(self, entry: CrealityCloudConfigEntry, key: str) -> None:
        super().__init__(entry, f"models_{key}")

    @property
    def models(self) -> dict[str, Any]:
        """Return the current upload data."""
        return self.coordinator.data.get("models") or {}

    @property
    def available(self) -> bool:
        """Do not affect account/printer entities when Models is unavailable."""
        return super().available and isinstance(self.coordinator.data.get("models"), dict)

    @property
    def device_info(self) -> DeviceInfo:
        """Link this device to the existing account hub."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}:models")},
            manufacturer="Creality Cloud",
            model="Creality Cloud Models",
            name="Creality Cloud Models · Dev",
            via_device_id=self.entry.runtime_data.account_device_id,
            configuration_url=self.entry.data.get("url"),
        )


class CrealityCloudPrinterEntity(CrealityCloudEntity):
    """Base entity attached to one configured printer."""

    def __init__(
        self,
        entry: CrealityCloudConfigEntry,
        printer_id: str,
        key: str,
    ) -> None:
        super().__init__(entry, f"printer_{printer_id}_{key}")
        self.printer_id = printer_id

    @property
    def printer(self) -> dict[str, Any]:
        """Return the latest printer payload."""
        return next(
            (
                printer
                for printer in self.coordinator.data.get("printers", [])
                if printer.get("id") == self.printer_id
            ),
            {},
        )

    @property
    def available(self) -> bool:
        """Keep the printer entity available while its profile exists."""
        return super().available and bool(self.printer)

    @property
    def device_info(self) -> DeviceInfo:
        """Return printer device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}:printer:{self.printer_id}")},
            manufacturer="Creality",
            model="Creality Cloud printer",
            name=str(self.printer.get("name") or self.printer_id) + " · Dev",
            via_device_id=self.entry.runtime_data.account_device_id,
            configuration_url=self.entry.data.get("url"),
        )
