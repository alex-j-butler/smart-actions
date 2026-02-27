"""Smart Actions integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ACTION_ID,
    DOMAIN,
    PLATFORMS,
    SERVICE_EXECUTE,
    SERVICE_RELOAD,
)
from .coordinator import SmartActionsCoordinator

_LOGGER = logging.getLogger(__name__)

# YAML config schema
ACTION_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("icon", default="mdi:lightning-bolt"): cv.string,
        vol.Optional("color", default="primary"): cv.string,
        vol.Optional("description", default=""): cv.string,
        vol.Optional("confirm", default=False): cv.boolean,
        vol.Optional("priority", default=50): vol.All(int, vol.Range(min=0, max=100)),
        vol.Optional("enabled", default=True): cv.boolean,
        vol.Optional("conditions", default=[]): list,
        vol.Optional("users", default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("action", default={}): dict,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("actions", default=[]): vol.All(
                    cv.ensure_list, [ACTION_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Smart Actions from YAML."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        hass.data[DOMAIN]["yaml_config"] = config[DOMAIN].get("actions", [])
    else:
        hass.data[DOMAIN]["yaml_config"] = []

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Actions from a config entry."""
    coordinator = SmartActionsCoordinator(hass)

    # Load UI actions from storage
    await coordinator.async_load()

    # Load YAML actions
    yaml_actions = hass.data[DOMAIN].get("yaml_config", [])
    if yaml_actions:
        coordinator.add_yaml_actions(yaml_actions)

    hass.data[DOMAIN]["coordinator"] = coordinator

    # Register services
    _register_services(hass, coordinator)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start condition tracking
    await coordinator.async_start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: SmartActionsCoordinator = hass.data[DOMAIN]["coordinator"]
    await coordinator.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop("coordinator", None)

    return unload_ok


def _register_services(
    hass: HomeAssistant, coordinator: SmartActionsCoordinator
) -> None:
    """Register integration services."""

    async def handle_execute(call: ServiceCall) -> None:
        """Handle the execute service call."""
        action_id = call.data[ATTR_ACTION_ID]
        success = await coordinator.async_execute_action(action_id)
        if not success:
            _LOGGER.warning("Failed to execute action: %s", action_id)

    async def handle_reload(call: ServiceCall) -> None:
        """Handle the reload service call."""
        # Re-read YAML config
        yaml_actions = hass.data[DOMAIN].get("yaml_config", [])
        await coordinator.async_reload_yaml(yaml_actions)
        _LOGGER.info("Smart Actions reloaded")

    async def handle_add_action(call: ServiceCall) -> None:
        """Handle adding/updating an action via service."""
        config = dict(call.data)
        action_id = config.get("id")

        if action_id and coordinator.get_action(action_id):
            await coordinator.async_update_action(action_id, config)
            _LOGGER.info("Updated smart action: %s", action_id)
        else:
            await coordinator.async_add_ui_action(config)
            _LOGGER.info("Added smart action: %s", action_id)

    async def handle_remove_action(call: ServiceCall) -> None:
        """Handle removing an action via service."""
        action_id = call.data[ATTR_ACTION_ID]
        removed = await coordinator.async_remove_action(action_id)
        if removed:
            _LOGGER.info("Removed smart action: %s", action_id)
        else:
            _LOGGER.warning("Action not found: %s", action_id)

    async def handle_set_enabled(call: ServiceCall) -> None:
        """Handle enabling/disabling an action."""
        action_id = call.data[ATTR_ACTION_ID]
        enabled = call.data["enabled"]
        action = coordinator.get_action(action_id)
        if action:
            action.enabled = enabled
            if action.source == "ui":
                await coordinator.async_save()
            await coordinator.async_evaluate_all()
            _LOGGER.info(
                "Action '%s' %s", action_id, "enabled" if enabled else "disabled"
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXECUTE,
        handle_execute,
        schema=vol.Schema({vol.Required(ATTR_ACTION_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RELOAD,
        handle_reload,
        schema=vol.Schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        "add_action",
        handle_add_action,
        schema=vol.Schema(
            {
                vol.Required("id"): cv.string,
                vol.Required("name"): cv.string,
                vol.Optional("icon"): cv.string,
                vol.Optional("color"): cv.string,
                vol.Optional("description"): cv.string,
                vol.Optional("confirm"): cv.boolean,
                vol.Optional("priority"): int,
                vol.Optional("users"): list,
                vol.Optional("conditions"): list,
                vol.Optional("action"): dict,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "remove_action",
        handle_remove_action,
        schema=vol.Schema({vol.Required(ATTR_ACTION_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "set_enabled",
        handle_set_enabled,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ACTION_ID): cv.string,
                vol.Required("enabled"): cv.boolean,
            }
        ),
    )
