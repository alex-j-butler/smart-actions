"""Config flow for Smart Actions."""

from __future__ import annotations

from json import dumps
from typing import Any

import voluptuous as vol
from dacite import Config
from homeassistant.config_entries import (
    HANDLERS,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult, section
from homeassistant.helpers.selector import (
    ActionSelector,
    ConditionSelector,
    EntitySelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.condition import async_validate_conditions_config

from custom_components.smart_actions.coordinator import SmartActionsCoordinator
from custom_components.smart_actions.helper import conditions_to_json
from custom_components.smart_actions.model import SmartAction

from .const import DOMAIN


def action_to_schema(action: dict[str, Any] | None):
    schema = {}
    if action is None:
        return None
    if action["action"] == "perform-action":
        schema = {
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
        schema = {
            "tap_action_type": "more-info",
            "tap_action_entity": {"tap_action_entity": action["entity"]},
        }

    return schema


def get_smart_action_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
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
        # Only allow one instance
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return SmartActionsOptionsFlow(config_entry)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"action": ActionSubentryFlow}


class ActionSubentryFlow(ConfigSubentryFlow):
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new smart action via UI."""
        if user_input is not None:
            coordinator = self.hass.data[DOMAIN]["coordinator"]

            # Parse users from comma-separated string
            users = []
            if user_input.get("users"):
                users = [u.strip() for u in user_input["users"].split(",") if u.strip()]

            tap_action = {}
            # Perform action
            if user_input["tap_action_type"] == "perform-action":
                service = user_input["tap_action_service"].get("tap_action_service")[0]
                tap_action = {
                    "action": "perform-action",
                    "perform_action": service.get("action"),
                    "target": service.get("target"),
                    "data": service.get("data"),
                }
            if user_input["tap_action_type"] == "more-info":
                entity = user_input["tap_action_entity"].get("tap_action_entity")
                tap_action = {"entity": entity}

            print("add: ", tap_action)

            conditions_raw = user_input.get("conditions")
            conditions = []
            if conditions_raw is not None:
                conditions = conditions_to_json(conditions_raw)

            config = {
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

            await coordinator.async_add_ui_action(config)
            return self.async_create_entry(title="", data=config)

        return self.async_show_form(
            step_id="user",
            data_schema=get_smart_action_schema(),
        )


class SmartActionsOptionsFlow(OptionsFlow):
    """Handle options for Smart Actions."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_menu(
            step_id="init",
            menu_options=["add_action", "edit_action_picker", "remove_action"],
        )

    async def async_step_add_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new smart action via UI."""
        if user_input is not None:
            coordinator = self.hass.data[DOMAIN]["coordinator"]

            # Parse users from comma-separated string
            users = []
            if user_input.get("users"):
                users = [u.strip() for u in user_input["users"].split(",") if u.strip()]

            tap_action = {}
            # Perform action
            if user_input["tap_action_type"] == "perform-action":
                service = user_input["tap_action_service"].get("tap_action_service")[0]
                tap_action = {
                    "action": "perform-action",
                    "perform_action": service.get("action"),
                    "target": service.get("target"),
                    "data": service.get("data"),
                }
            if user_input["tap_action_type"] == "more-info":
                entity = user_input["tap_action_entity"].get("tap_action_entity")
                tap_action = {"entity": entity}

            print("add: ", tap_action)

            conditions_raw = user_input.get("conditions")
            conditions = []
            if conditions_raw is not None:
                conditions = conditions_to_json(conditions_raw)

            config = {
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

            await coordinator.async_add_ui_action(config)
            return self.async_create_entry(title="", data=self._config_entry.options)

        return self.async_show_form(
            step_id="add_action",
            data_schema=get_smart_action_schema(),
        )

    async def async_step_edit_action(
        self,
        user_input: dict[str, Any] | None = None,
        action: SmartAction | None = None,
    ) -> ConfigFlowResult:
        coordinator: SmartActionsCoordinator = self.hass.data[DOMAIN]["coordinator"]
        if user_input is not None:
            # Parse users from comma-separated string
            users = []
            if user_input.get("users"):
                users = [u.strip() for u in user_input["users"].split(",") if u.strip()]

            tap_action = {}
            # Perform action
            if user_input["tap_action_type"] == "perform-action":
                service = user_input["tap_action_service"].get("tap_action_service")[0]
                tap_action = {
                    "action": "perform-action",
                    "perform_action": service.get("action"),
                    "target": service.get("target"),
                    "data": service.get("data"),
                }
            if user_input["tap_action_type"] == "more-info":
                entity = user_input["tap_action_entity"].get("tap_action_entity")
                tap_action = {"entity": entity}

            conditions_raw = user_input.get("conditions")
            conditions = []
            if conditions_raw is not None:
                conditions = conditions_to_json(conditions_raw)

            config = {
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

            await coordinator.async_update_action(
                user_input["id"],
                config,
            )
            return self.async_create_entry(title="", data=self._config_entry.options)
            # return self.async_abort(reason="na")

        if action is None:
            return self.async_abort(reason="No action selected")

        conditions_object = await async_validate_conditions_config(
            self.hass, action.conditions
        )

        return self.async_show_form(
            step_id="edit_action",
            data_schema=self.add_suggested_values_to_schema(
                get_smart_action_schema(),
                {
                    "id": action.id,
                    "name": action.name,
                    "icon": action.icon,
                    "description": action.description,
                    "priority": action.priority,
                    "users": ",".join(action.users),
                    "conditions": conditions_object,
                    # "tap_action": ,
                    "icon_tap_action": action.icon_tap_action,
                }
                | (action_to_schema(action.tap_action) or {}),
            ),
        )

    async def async_step_edit_action_picker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a smart action."""
        coordinator = self.hass.data[DOMAIN]["coordinator"]

        if user_input is not None:
            action_id = user_input["action_id"]
            # await coordinator.async_remove_action(action_id)
            # return self.async_create_entry(title="", data=self._config_entry.options)
            action = coordinator.actions[action_id]
            return await self.async_step_edit_action(action=action)

        ui_actions = {aid: a.name for aid, a in coordinator.actions.items()}

        if not ui_actions:
            return self.async_abort(reason="no_actions")

        return self.async_show_form(
            step_id="edit_action_picker",
            data_schema=vol.Schema(
                {
                    vol.Required("action_id"): vol.In(ui_actions),
                }
            ),
        )

    async def async_step_remove_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a smart action."""
        coordinator = self.hass.data[DOMAIN]["coordinator"]

        if user_input is not None:
            action_id = user_input["action_id"]
            await coordinator.async_remove_action(action_id)
            return self.async_create_entry(title="", data=self._config_entry.options)

        ui_actions = {aid: a.name for aid, a in coordinator.actions.items()}

        if not ui_actions:
            return self.async_abort(reason="no_actions")

        return self.async_show_form(
            step_id="remove_action",
            data_schema=vol.Schema(
                {
                    vol.Required("action_id"): vol.In(ui_actions),
                }
            ),
        )
