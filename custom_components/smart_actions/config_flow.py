"""Config flow for Smart Actions."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    ActionSelector,
    ConditionSelector,
    EntitySelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from custom_components.smart_actions.helper import conditions_to_json

from .const import DOMAIN


def action_to_schema(action: dict[str, Any] | None) -> dict[str, Any] | None:
    if not action or not action.get("action"):
        return None
    if action["action"] == "perform-action":
        return {
            "tap_action_type": "perform-action",
            "tap_action_service": {
                "tap_action_service": [
                    {
                        "action": action["perform_action"],
                        "target": action["target"],
                    }
                ]
            },
        }
    if action["action"] == "more-info":
        return {
            "tap_action_type": "more-info",
            "tap_action_entity": {"tap_action_entity": action["entity"]},
        }
    return None


def get_smart_action_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("id"): str,
            vol.Required("name"): str,
            vol.Optional("icon", default="mdi:lightning-bolt"): str,
            vol.Optional("color", default="primary"): str,
            vol.Optional("description", default=""): str,
            vol.Required("conditions"): ConditionSelector(),
            vol.Optional("tap_action_type"): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": "perform-action",
                            "label": "Call a service",
                        },
                        {"value": "navigate", "label": "Navigate"},
                        {"value": "more-info", "label": "More info"},
                        {"value": "url", "label": "Open URL"},
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                ),
            ),
            vol.Required("tap_action_service"): section(
                vol.Schema(
                    {
                        vol.Optional("tap_action_service"): ActionSelector(),
                    }
                )
            ),
            vol.Required("tap_action_navigate"): section(
                vol.Schema(
                    {
                        vol.Optional("tap_action_navigation_path"): TextSelector(),
                    }
                )
            ),
            vol.Required("tap_action_entity"): section(
                vol.Schema(
                    {
                        vol.Optional("tap_action_entity"): EntitySelector(),
                    }
                )
            ),
            vol.Required("tap_action_url"): section(
                vol.Schema(
                    {
                        vol.Optional("tap_action_url"): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.URL)
                        ),
                    }
                )
            ),
            vol.Optional("icon_tap_action"): ActionSelector(),
            vol.Optional("confirm", default=False): bool,
            vol.Optional("priority", default=50): vol.All(
                int, vol.Range(min=0, max=100)
            ),
            vol.Optional("users", default=""): str,
        }
    )


class SmartActionsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Actions."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Smart Actions",
                data={},
            )

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "info": "This will set up the Smart Actions integration."
            },
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"action": ActionSubentryFlow}


class ActionSubentryFlow(ConfigSubentryFlow):
    """Handle add/edit of a smart action as a config subentry."""

    def _process_user_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Convert raw form input into a stored action config dict."""
        users = []
        if user_input.get("users"):
            users = [u.strip() for u in user_input["users"].split(",") if u.strip()]

        tap_action: dict[str, Any] = {}
        action_type = user_input.get("tap_action_type")
        if action_type == "perform-action":
            service_list = user_input["tap_action_service"].get("tap_action_service")
            if service_list:
                service = service_list[0]
                tap_action = {
                    "action": "perform-action",
                    "perform_action": service.get("action"),
                    "target": service.get("target"),
                    "data": service.get("data"),
                }
        elif action_type == "more-info":
            entity = user_input["tap_action_entity"].get("tap_action_entity")
            tap_action = {"action": "more-info", "entity": entity}

        conditions_raw = user_input.get("conditions")
        conditions = conditions_to_json(conditions_raw) if conditions_raw else []

        return {
            "id": user_input["id"],
            "name": user_input["name"],
            "icon": user_input.get("icon", "mdi:lightning-bolt"),
            "color": user_input.get("color", "primary"),
            "description": user_input.get("description", ""),
            "confirm": user_input.get("confirm", False),
            "priority": user_input.get("priority", 50),
            "users": users,
            "conditions": conditions,
            "tap_action": tap_action,
            "icon_tap_action": user_input.get("icon_tap_action", {}),
        }

    def _build_suggested_values(self, action_data: dict[str, Any]) -> dict[str, Any]:
        """
        Build suggested form values from stored action data.

        Conditions are passed as raw JSON dicts (not compiled Template objects)
        so the ConditionSelector can display them correctly.
        """
        values: dict[str, Any] = {
            "id": action_data.get("id", ""),
            "name": action_data.get("name", ""),
            "icon": action_data.get("icon", "mdi:lightning-bolt"),
            "color": action_data.get("color", "primary"),
            "description": action_data.get("description", ""),
            "priority": action_data.get("priority", 50),
            "users": ",".join(action_data.get("users", [])),
            "conditions": action_data.get("conditions", []),
            "icon_tap_action": action_data.get("icon_tap_action", {}),
            "confirm": action_data.get("confirm", False),
        }
        tap_action = action_data.get("tap_action")
        if tap_action:
            values.update(action_to_schema(tap_action) or {})
        return values

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new smart action."""
        if user_input is not None:
            config = self._process_user_input(user_input)
            coordinator = self.hass.data[DOMAIN]["coordinator"]
            await coordinator.async_add_ui_action(config)
            return self.async_create_entry(title=config["name"], data=config)

        return self.async_show_form(
            step_id="user",
            data_schema=get_smart_action_schema(),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing smart action."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            config = self._process_user_input(user_input)
            coordinator = self.hass.data[DOMAIN]["coordinator"]
            await coordinator.async_update_action(config["id"], config)
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=config["name"],
                data=config,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                get_smart_action_schema(),
                self._build_suggested_values(dict(subentry.data)),
            ),
        )
