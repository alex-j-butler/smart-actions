"""Smart Action data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.smart_actions.helper import conditions_from_json


@dataclass
class SmartAction:
    """Represents a single smart action.

    Fields:
      action: The service call to execute (used by smart_actions.execute).
      tap_action: Frontend tap behaviour sent to the card. Supports:
        - call-service / perform-action  (default, derived from ``action``)
        - navigate  (e.g. open a bubble-card popup)
        - more-info (open entity detail dialog)
        - url       (open external link)
      icon_tap_action: Optional separate behaviour when the icon is tapped.
      entity: Optional HA entity to associate with the action row (e.g. for
              more-info on icon tap).
    """

    id: str
    name: str
    icon: str = "mdi:lightning-bolt"
    color: str = "primary"
    description: str = ""
    confirm: bool = False
    priority: int = 50
    enabled: bool = True
    conditions: list[dict[str, Any]] = field(default_factory=list)
    users: list[str] = field(default_factory=list)
    action: dict[str, Any] = field(default_factory=dict)
    tap_action: dict[str, Any] | None = None
    icon_tap_action: dict[str, Any] | None = None
    entity: str | None = None
    source: str = "yaml"  # "yaml" or "ui"

    # Runtime state
    _active: bool = False

    @property
    def active(self) -> bool:
        """Return whether conditions are currently met."""
        return self._active and self.enabled

    @active.setter
    def active(self, value: bool) -> None:
        """Set the active state."""
        self._active = value

    def is_visible_to_user(self, user_id: str | None) -> bool:
        """Check if this action should be visible to a specific user."""
        if not self.users:
            return True
        if user_id is None:
            return True
        return user_id in self.users

    def _resolve_tap_action(self) -> dict[str, Any]:
        """Build the tap_action dict the card should use.

        Priority:
        1. Explicit ``tap_action`` defined in config.
        2. Auto-generated from ``action`` service config.
        3. Fallback to smart_actions.execute (the card default).
        """
        if self.tap_action:
            return self.tap_action

        if self.action and self.action.get("service"):
            return {
                "action": "perform-action",
                "perform_action": self.action["service"],
                **({"data": self.action["data"]} if self.action.get("data") else {}),
                **(
                    {"service_data": self.action["service_data"]}
                    if self.action.get("service_data")
                    else {}
                ),
                **(
                    {"target": self.action["target"]}
                    if self.action.get("target")
                    else {}
                ),
            }

        # Card will fall back to smart_actions.execute
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for sensor attributes / card consumption."""
        data = {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "color": self.color,
            "description": self.description,
            "confirm": self.confirm,
            "priority": self.priority,
            "enabled": self.enabled,
            "active": self.active,
            "users": self.users,
            "source": self.source,
        }

        # Include resolved tap actions so the card doesn't need overrides
        resolved_tap = self._resolve_tap_action()
        if resolved_tap:
            data["tap_action"] = resolved_tap

        if self.icon_tap_action:
            data["icon_tap_action"] = self.icon_tap_action

        if self.entity:
            data["entity"] = self.entity

        return data

    @classmethod
    def from_config(
        cls, hass: HomeAssistant, config: dict[str, Any], source: str = "yaml"
    ) -> SmartAction:
        """Create a SmartAction from a config dict."""
        return cls(
            id=config["id"],
            name=config.get("name", config["id"].replace("_", " ").title()),
            icon=config.get("icon", "mdi:lightning-bolt"),
            color=config.get("color", "primary"),
            description=config.get("description", ""),
            confirm=config.get("confirm", False),
            priority=config.get("priority", 50),
            enabled=config.get("enabled", True),
            conditions=conditions_from_json(
                hass=hass, conditions=config.get("conditions", [])
            ),
            users=config.get("users", []),
            action=config.get("action", {}),
            tap_action=config.get("tap_action"),
            icon_tap_action=config.get("icon_tap_action"),
            entity=config.get("entity"),
            source=source,
        )
