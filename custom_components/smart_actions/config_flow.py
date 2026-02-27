"""Config flow for Smart Actions."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class SmartActionsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Actions."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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


class SmartActionsOptionsFlow(OptionsFlow):
    """Handle options for Smart Actions."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_menu(
            step_id="init",
            menu_options=["add_action", "remove_action"],
        )

    async def async_step_add_action(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new smart action via UI."""
        if user_input is not None:
            coordinator = self.hass.data[DOMAIN]["coordinator"]

            # Parse users from comma-separated string
            users = []
            if user_input.get("users"):
                users = [u.strip() for u in user_input["users"].split(",") if u.strip()]

            config = {
                "id": user_input["id"],
                "name": user_input["name"],
                "icon": user_input.get("icon", "mdi:lightning-bolt"),
                "color": user_input.get("color", "primary"),
                "description": user_input.get("description", ""),
                "confirm": user_input.get("confirm", False),
                "priority": user_input.get("priority", 50),
                "users": users,
                "conditions": [],  # Conditions need to be set via service/YAML
                "action": {},  # Action needs to be set via service/YAML
            }

            await coordinator.async_add_ui_action(config)
            return self.async_create_entry(title="", data=self._config_entry.options)

        return self.async_show_form(
            step_id="add_action",
            data_schema=vol.Schema(
                {
                    vol.Required("id"): str,
                    vol.Required("name"): str,
                    vol.Optional("icon", default="mdi:lightning-bolt"): str,
                    vol.Optional("color", default="primary"): str,
                    vol.Optional("description", default=""): str,
                    vol.Optional("confirm", default=False): bool,
                    vol.Optional("priority", default=50): vol.All(
                        int, vol.Range(min=0, max=100)
                    ),
                    vol.Optional("users", default=""): str,
                }
            ),
        )

    async def async_step_remove_action(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a smart action."""
        coordinator = self.hass.data[DOMAIN]["coordinator"]

        if user_input is not None:
            action_id = user_input["action_id"]
            await coordinator.async_remove_action(action_id)
            return self.async_create_entry(title="", data=self._config_entry.options)

        ui_actions = {
            aid: a.name
            for aid, a in coordinator.actions.items()
        }

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
