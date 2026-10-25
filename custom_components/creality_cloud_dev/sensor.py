"""Sensors exposed by Creality Cloud."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrealityCloudConfigEntry
from .entity import CrealityCloudEntity, CrealityCloudModelsEntity, CrealityCloudPrinterEntity


@dataclass(frozen=True, kw_only=True)
class CrealityCloudSensorDescription(SensorEntityDescription):
    """Describe a value in the coordinator payload."""

    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


ACCOUNT_SENSORS = (
    CrealityCloudSensorDescription(
        key="session",
        translation_key="session",
        icon="mdi:account-key",
        device_class=SensorDeviceClass.ENUM,
        options=["open", "closed"],
        value_fn=lambda data: data.get("session", {}).get("state", "closed"),
        attributes_fn=lambda data: session_attributes(data),
    ),
    CrealityCloudSensorDescription(
        key="points_total",
        translation_key="points_total",
        icon="mdi:star-circle",
        native_unit_of_measurement="points",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("points", {}).get("total"),
    ),
    CrealityCloudSensorDescription(
        key="points_today",
        translation_key="points_today",
        icon="mdi:star-plus",
        native_unit_of_measurement="points",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("points", {}).get("earnedToday"),
    ),
    CrealityCloudSensorDescription(
        key="lottery_tickets",
        translation_key="lottery_tickets",
        icon="mdi:ticket-confirmation",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("rewards", {}).get("lotteryTickets"),
    ),
    CrealityCloudSensorDescription(
        key="boosts_available",
        translation_key="boosts_available",
        icon="mdi:rocket-launch",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("rewards", {}).get("boostsAvailable"),
    ),
    CrealityCloudSensorDescription(
        key="latest_order",
        translation_key="latest_order",
        icon="mdi:package-variant-closed",
        value_fn=lambda data: (
            data.get("orders", {}).get("latest") or {}
        ).get("status"),
        attributes_fn=lambda data: latest_order_attributes(data),
    ),
)

PRINTER_SENSOR_KEYS = ("status", "daily_count", "last_run", "next_run", "last_gcode")
MODELS_SENSOR_KEYS = ("default_category", "available", "last_model_upload", "last_upload", "next_upload", "uploads_today")


async def async_setup_entry(
    hass,
    entry: CrealityCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up account and dynamically discovered printer sensors."""
    async_add_entities(
        CrealityCloudSensor(entry, description) for description in ACCOUNT_SENSORS
    )
    async_add_entities(CrealityCloudModelsSensor(entry, key) for key in MODELS_SENSOR_KEYS)
    known_printers: set[str] = set()

    @callback
    def add_printers() -> None:
        new_ids = {
            str(printer.get("id"))
            for printer in entry.runtime_data.coordinator.data.get("printers", [])
            if printer.get("id") and printer.get("id") not in known_printers
        }
        if not new_ids:
            return
        known_printers.update(new_ids)
        async_add_entities(
            CrealityCloudPrinterSensor(entry, printer_id, key)
            for printer_id in new_ids
            for key in PRINTER_SENSOR_KEYS
        )

    add_printers()
    entry.async_on_unload(
        entry.runtime_data.coordinator.async_add_listener(add_printers)
    )


class CrealityCloudSensor(CrealityCloudEntity, SensorEntity):
    """Generic account sensor."""

    entity_description: CrealityCloudSensorDescription

    def __init__(self, entry, description: CrealityCloudSensorDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        """Return the latest value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        """Return useful diagnostics without exposing private configuration."""
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.coordinator.data)
        return None


class CrealityCloudModelsSensor(CrealityCloudModelsEntity, SensorEntity):
    """Model uploads and saved library configuration."""

    def __init__(self, entry, key: str) -> None:
        super().__init__(entry, key)
        self.key = key
        self._attr_translation_key = f"models_{key}"
        if key in {"last_upload", "next_upload"}:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = {
            "default_category": "mdi:shape",
            "available": "mdi:cube-outline",
            "last_model_upload": "mdi:cube-send",
            "last_upload": "mdi:history",
            "next_upload": "mdi:clock-outline",
            "uploads_today": "mdi:counter",
        }[key]

    @property
    def native_value(self):
        """Return successful deliveries, not attempts or reward points."""
        if self.key == "default_category":
            category = self.models.get("defaultCategory") or {}
            parts = (category.get("category"), category.get("subcategory"))
            return " / ".join(parts) if all(parts) else None
        if self.key == "available":
            return self.models.get("availableCount")
        if self.key == "last_model_upload":
            name = (self.models.get("lastModel") or {}).get("name")
            return str(name)[:255] if name else None
        if self.key == "last_upload":
            return parse_datetime(self.models.get("lastUploadAt"))
        if self.key == "next_upload":
            return parse_datetime(self.models.get("nextUploadAt")) if self.models.get("enabled") else None
        return self.models.get("uploadsToday")

    @property
    def extra_state_attributes(self):
        """Expose model details and inventory freshness."""
        if self.key == "last_model_upload":
            model = self.models.get("lastModel") or {}
            return {"name": model.get("name"), "model_id": model.get("id"), "url": model.get("url")}
        if self.key == "available":
            return {"scanned_at": self.models.get("scannedAt"), "library_error": self.models.get("libraryError")}
        if self.key == "uploads_today":
            return {"daily_limit": self.models.get("dailyLimit"), "timezone": self.models.get("timezone")}
        return None


class CrealityCloudPrinterSensor(CrealityCloudPrinterEntity, SensorEntity):
    """Sensor associated with a printer profile."""

    def __init__(self, entry, printer_id: str, key: str) -> None:
        super().__init__(entry, printer_id, key)
        self.key = key
        self._attr_translation_key = f"printer_{key}"
        if key in {"last_run", "next_run"}:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        if key == "status":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["ready", "disabled", "unavailable"]
        self._attr_icon = {
            "status": "mdi:printer-3d",
            "daily_count": "mdi:counter",
            "last_run": "mdi:history",
            "next_run": "mdi:clock-outline",
            "last_gcode": "mdi:file-code",
        }[key]

    @property
    def native_value(self):
        """Return the current printer value."""
        if self.key == "status":
            if not self.printer.get("enabled"):
                return "disabled"
            return "ready" if self.printer.get("available") else "unavailable"
        if self.key == "daily_count":
            return self.printer.get("dailyCount")
        if self.key == "last_run":
            return parse_datetime(self.printer.get("lastRunAt"))
        if self.key == "next_run":
            return parse_datetime(self.printer.get("nextRunAt"))
        return self.printer.get("lastGcode") or None

    @property
    def extra_state_attributes(self):
        """Expose the daily print limit and last result."""
        if self.key == "daily_count":
            return {"daily_limit": self.printer.get("dailyLimit")}
        if self.key == "status":
            return {"last_status": self.printer.get("lastStatus")}
        return None


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp for a timestamp sensor."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def latest_order_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """Return useful details about the most recently created shop order."""
    order = data.get("orders", {}).get("latest")
    if not isinstance(order, dict):
        return {}
    return {
        "order_id": order.get("id"),
        "order_number": order.get("orderNumber"),
        "product": order.get("title"),
        "points": order.get("points"),
        "quantity": order.get("quantity"),
        "region": order.get("region"),
        "status_kind": order.get("statusKind"),
        "created_at": order.get("createdAt"),
        "updated_at": order.get("updatedAt"),
        "image_url": order.get("imageUrl"),
    }


def session_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """Return the last session check without exposing authentication data."""
    session = data.get("session", {})
    return {
        "checked_at": session.get("checkedAt") or None,
        "reason": session.get("reason") or None,
    }
