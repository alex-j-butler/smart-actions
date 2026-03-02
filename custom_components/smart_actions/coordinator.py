"""Coordinator for Smart Actions."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_time_interval,
    async_track_state_change_event,
)
from homeassistant.helpers.storage import Store

from .const import DOMAIN, EVENT_ACTION_STATE_CHANGED
from .conditions import async_evaluate_conditions, evaluate_conditions
from .model import SmartAction

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.actions"
STORAGE_VERSION = 1
SCAN_INTERVAL = timedelta(seconds=30)


class SmartActionsCoordinator:
    """Manage all smart actions and their state."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the coordinator."""
        self.hass = hass
        self._actions: dict[str, SmartAction] = {}
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._listeners: list[Any] = []
        self._update_callbacks: list[Any] = []
        self._tracked_entities: set[str] = set()
        self._unsub_state_listeners: list[Any] = []

    @property
    def actions(self) -> dict[str, SmartAction]:
        """Return all registered actions."""
        return self._actions

    def get_action(self, action_id: str) -> SmartAction | None:
        """Get a specific action by ID."""
        return self._actions.get(action_id)

    def get_active_actions(self, user_id: str | None = None) -> list[SmartAction]:
        """Get all currently active actions, optionally filtered by user."""
        active = [a for a in self._actions.values() if a.active]
        if user_id:
            active = [a for a in active if a.is_visible_to_user(user_id)]
        active.sort(key=lambda a: a.priority)
        return active

    def get_all_actions_for_user(self, user_id: str | None = None) -> list[SmartAction]:
        """Get all actions visible to a user (active or not)."""
        actions = list(self._actions.values())
        if user_id:
            actions = [a for a in actions if a.is_visible_to_user(user_id)]
        actions.sort(key=lambda a: a.priority)
        return actions

    async def async_load(self) -> None:
        """Load UI-defined actions from storage."""
        stored = await self._store.async_load()
        if stored and "actions" in stored:
            for action_data in stored["actions"]:
                action = SmartAction.from_config(action_data, source="ui")
                self._actions[action.id] = action
            _LOGGER.debug("Loaded %d UI actions from storage", len(stored["actions"]))

    async def async_save(self) -> None:
        """Save UI-defined actions to storage."""
        ui_actions = [
            a.to_dict()
            | {
                "conditions": a.conditions,
                "action": a.action,
            }
            for a in self._actions.values()
            if a.source == "ui"
        ]
        await self._store.async_save({"actions": ui_actions})

    def add_yaml_actions(self, actions: list[dict[str, Any]]) -> None:
        """Add actions from YAML configuration."""
        for action_config in actions:
            action = SmartAction.from_config(action_config, source="yaml")
            self._actions[action.id] = action
        _LOGGER.debug("Added %d YAML actions", len(actions))

    async def async_add_ui_action(self, config: dict[str, Any]) -> SmartAction:
        """Add an action from the UI."""
        action = SmartAction.from_config(config, source="ui")
        self._actions[action.id] = action
        await self.async_save()
        self._update_entity_tracking()
        await self.async_evaluate_all()
        return action

    async def async_remove_action(self, action_id: str) -> bool:
        """Remove an action."""
        if action_id in self._actions:
            del self._actions[action_id]
            await self.async_save()
            self._update_entity_tracking()
            self._notify_update()
            return True
        return False

    async def async_update_action(
        self, action_id: str, config: dict[str, Any]
    ) -> SmartAction | None:
        """Update an existing action."""
        existing = self._actions.get(action_id)
        if not existing:
            return None

        source = existing.source
        action = SmartAction.from_config(config, source=source)
        self._actions[action_id] = action

        if source == "ui":
            await self.async_save()

        self._update_entity_tracking()
        await self.async_evaluate_all()
        return action

    async def async_execute_action(self, action_id: str) -> bool:
        """Execute a smart action's service call."""
        action = self._actions.get(action_id)
        if not action:
            _LOGGER.warning("Action not found: %s", action_id)
            return False

        if not action.active:
            _LOGGER.warning("Action is not active: %s", action_id)
            return False

        service_config = action.action
        if not service_config:
            _LOGGER.warning("Action has no service configured: %s", action_id)
            return False

        service = service_config.get("service", "")
        if "." not in service:
            _LOGGER.error("Invalid service format: %s", service)
            return False

        domain, service_name = service.split(".", 1)
        service_data = service_config.get(
            "data", service_config.get("service_data", {})
        )
        target = service_config.get("target", {})

        try:
            await self.hass.services.async_call(
                domain,
                service_name,
                service_data,
                target=target,
                blocking=True,
            )
            self.hass.bus.async_fire(
                "smart_actions_action_executed",
                {"action_id": action_id, "action_name": action.name},
            )
            _LOGGER.info("Executed smart action: %s", action_id)
            return True
        except Exception:
            _LOGGER.exception("Failed to execute action: %s", action_id)
            return False

    async def async_start(self) -> None:
        """Start tracking conditions."""
        self._update_entity_tracking()

        # Periodic evaluation for time-based conditions
        self._listeners.append(
            async_track_time_interval(
                self.hass, self._async_periodic_update, SCAN_INTERVAL
            )
        )

        # Initial evaluation
        await self.async_evaluate_all()

    async def async_stop(self) -> None:
        """Stop tracking."""
        for unsub in self._listeners:
            unsub()
        self._listeners.clear()

        for unsub in self._unsub_state_listeners:
            unsub()
        self._unsub_state_listeners.clear()

    def _update_entity_tracking(self) -> None:
        """Update which entities we track for state changes."""
        # Unsubscribe old listeners
        for unsub in self._unsub_state_listeners:
            unsub()
        self._unsub_state_listeners.clear()

        # Collect all entity_ids referenced in conditions
        entities: set[str] = set()
        for action in self._actions.values():
            entities.update(self._extract_entities(action.conditions))

        if entities:
            self._unsub_state_listeners.append(
                async_track_state_change_event(
                    self.hass,
                    list(entities),
                    self._async_state_changed,
                )
            )
        self._tracked_entities = entities
        _LOGGER.debug("Tracking %d entities for conditions", len(entities))

    def _extract_entities(self, conditions: list[dict[str, Any]]) -> set[str]:
        """Extract entity IDs from conditions recursively."""
        entities: set[str] = set()
        for cond in conditions:
            entity_id = cond.get("entity_id")
            if entity_id:
                if isinstance(entity_id, list):
                    entities.update(entity_id)
                else:
                    entities.add(entity_id)
            # Recurse into nested conditions (or/and/not)
            nested = cond.get("conditions", [])
            entities.update(self._extract_entities(nested))
        return entities

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state change of a tracked entity."""
        self.hass.async_create_task(self.async_evaluate_all())

    async def _async_periodic_update(self, now) -> None:
        """Periodic condition evaluation (for time-based conditions)."""
        await self.async_evaluate_all()

    async def async_evaluate_all(self) -> None:
        """Re-evaluate all action conditions."""
        changed = False
        for action in self._actions.values():
            was_active = action.active
            action.active = await async_evaluate_conditions(
                self.hass, action.conditions
            )
            if action.active != was_active:
                changed = True
                _LOGGER.debug(
                    "Action '%s' changed: %s -> %s",
                    action.id,
                    was_active,
                    action.active,
                )

        if changed:
            self._notify_update()

    def register_update_callback(self, callback) -> None:
        """Register a callback for state updates."""
        self._update_callbacks.append(callback)

    def unregister_update_callback(self, callback) -> None:
        """Unregister an update callback."""
        self._update_callbacks = [c for c in self._update_callbacks if c != callback]

    @callback
    def _notify_update(self) -> None:
        """Notify all registered callbacks of an update."""
        for cb in self._update_callbacks:
            cb()

    async def async_reload_yaml(self, actions: list[dict[str, Any]]) -> None:
        """Reload YAML actions (remove old YAML ones, add new)."""
        yaml_ids = [a["id"] for a in actions]

        # Remove old YAML actions
        to_remove = [
            aid
            for aid, a in self._actions.items()
            if a.source == "yaml" and aid not in yaml_ids
        ]
        for aid in to_remove:
            del self._actions[aid]

        # Add/update YAML actions
        self.add_yaml_actions(actions)

        self._update_entity_tracking()
        await self.async_evaluate_all()
