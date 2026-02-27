"""Sensor platform for Smart Actions."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SmartActionsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: SmartActionsCoordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([
        SmartActionsSensor(coordinator),
    ])


class SmartActionsSensor(SensorEntity):
    """Sensor showing count of active smart actions with filterable attributes."""

    _attr_has_entity_name = False
    _attr_unique_id = "smart_actions_summary"
    _attr_name = "Smart Actions"
    _attr_icon = "mdi:lightning-bolt-outline"

    def __init__(self, coordinator: SmartActionsCoordinator) -> None:
        """Initialise the sensor."""
        self._coordinator = coordinator

    @property
    def native_value(self) -> int:
        """Return the number of currently active actions."""
        return len(self._coordinator.get_active_actions())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all actions grouped for easy filtering.

        Attributes:
          active_actions: list of active action dicts (all users)
          all_actions: list of all action dicts (active or not)
          active_count: number of active actions
          user_{person_entity_id}: list of active action dicts for that user
          action_ids: list of all active action IDs
        """
        active = self._coordinator.get_active_actions()
        all_actions = list(self._coordinator.actions.values())

        attrs: dict[str, Any] = {
            "active_count": len(active),
            "active_actions": [a.to_dict() for a in active],
            "all_actions": [a.to_dict() for a in all_actions],
            "active_action_ids": [a.id for a in active],
        }

        # Build per-user filtered lists
        # Collect all unique user IDs across all actions
        all_user_ids: set[str] = set()
        for action in all_actions:
            all_user_ids.update(action.users)

        for user_id in all_user_ids:
            user_active = self._coordinator.get_active_actions(user_id=user_id)
            attrs[f"user_{user_id}"] = [a.to_dict() for a in user_active]
            attrs[f"user_{user_id}_count"] = len(user_active)

        return attrs

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        self._coordinator.register_update_callback(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister update callback."""
        self._coordinator.unregister_update_callback(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()
