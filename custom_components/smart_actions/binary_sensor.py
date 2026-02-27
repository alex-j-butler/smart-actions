"""Binary sensor platform for Smart Actions."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up binary sensors from a config entry."""
    coordinator: SmartActionsCoordinator = hass.data[DOMAIN]["coordinator"]

    entities: dict[str, SmartActionBinarySensor] = {}

    @callback
    def _async_update_entities() -> None:
        """Add new entities and update existing ones."""
        new_entities = []

        for action_id, action in coordinator.actions.items():
            if action_id not in entities:
                entity = SmartActionBinarySensor(coordinator, action_id)
                entities[action_id] = entity
                new_entities.append(entity)
            else:
                entities[action_id].async_write_ha_state()

        # Remove entities for deleted actions
        removed = set(entities.keys()) - set(coordinator.actions.keys())
        for action_id in removed:
            entity = entities.pop(action_id)
            entity.async_remove()

        if new_entities:
            async_add_entities(new_entities)

    coordinator.register_update_callback(_async_update_entities)

    # Create initial entities
    _async_update_entities()


class SmartActionBinarySensor(BinarySensorEntity):
    """Binary sensor for an individual smart action."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: SmartActionsCoordinator,
        action_id: str,
    ) -> None:
        """Initialise the binary sensor."""
        self._coordinator = coordinator
        self._action_id = action_id
        action = coordinator.get_action(action_id)

        self._attr_unique_id = f"smart_action_{action_id}"
        self._attr_name = f"Smart Action {action.name}" if action else action_id

    @property
    def is_on(self) -> bool | None:
        """Return true if the action conditions are met."""
        action = self._coordinator.get_action(self._action_id)
        if action is None:
            return None
        return action.active

    @property
    def icon(self) -> str:
        """Return the icon."""
        action = self._coordinator.get_action(self._action_id)
        return action.icon if action else "mdi:lightning-bolt"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        action = self._coordinator.get_action(self._action_id)
        if not action:
            return {}

        return {
            "action_id": action.id,
            "description": action.description,
            "color": action.color,
            "confirm": action.confirm,
            "priority": action.priority,
            "users": action.users,
            "enabled": action.enabled,
            "source": action.source,
        }

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
