"""Condition evaluation for Smart Actions."""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    async_from_config,
    async_validate_conditions_config,
)
from homeassistant.helpers.template import Template

_LOGGER = logging.getLogger(__name__)


async def async_evaluate_conditions(
    hass: HomeAssistant, conditions: list[dict]
) -> bool:
    """Evaluate conditions using HA's built-in condition engine."""
    if not conditions:
        return True

    try:
        # Validate the condition configs first
        validated = await async_validate_conditions_config(hass, conditions)

        # Build a combined AND test from all conditions
        # async_from_config returns a ConditionCheckerType callable
        test_funcs = []
        for conf in validated:
            test = await async_from_config(hass, conf)
            test_funcs.append(test)

        # Evaluate all (AND logic)
        for test in test_funcs:
            if not test(hass):
                return False
        return True

    except Exception:
        _LOGGER.exception("Error evaluating conditions")
        return False


def evaluate_conditions(hass: HomeAssistant, conditions: list[dict[str, Any]]) -> bool:
    """Evaluate a list of conditions. All must be true (AND logic)."""
    if not conditions:
        return True

    for condition in conditions:
        if not _evaluate_single_condition(hass, condition):
            return False
    return True


def _evaluate_single_condition(hass: HomeAssistant, condition: dict[str, Any]) -> bool:
    """Evaluate a single condition."""
    cond_type = condition.get("condition", "state")

    try:
        if cond_type == "state":
            return _eval_state_condition(hass, condition)
        elif cond_type == "numeric_state":
            return _eval_numeric_state_condition(hass, condition)
        elif cond_type == "time":
            return _eval_time_condition(hass, condition)
        elif cond_type == "template":
            return _eval_template_condition(hass, condition)
        elif cond_type == "or":
            return _eval_or_condition(hass, condition)
        elif cond_type == "and":
            return _eval_and_condition(hass, condition)
        elif cond_type == "not":
            return _eval_not_condition(hass, condition)
        else:
            _LOGGER.warning("Unknown condition type: %s", cond_type)
            return False
    except Exception:
        _LOGGER.exception("Error evaluating condition: %s", condition)
        return False


def _eval_state_condition(hass: HomeAssistant, condition: dict[str, Any]) -> bool:
    """Evaluate a state condition."""
    entity_id = condition.get("entity_id")
    if not entity_id:
        return False

    state = hass.states.get(entity_id)
    if state is None:
        return False

    current = state.state
    target_state = condition.get("state")
    target_not = condition.get("state_not")

    if target_state is not None:
        if isinstance(target_state, list):
            return current in [str(s) for s in target_state]
        return current == str(target_state)

    if target_not is not None:
        if isinstance(target_not, list):
            return current not in [str(s) for s in target_not]
        return current != str(target_not)

    return False


def _eval_numeric_state_condition(
    hass: HomeAssistant, condition: dict[str, Any]
) -> bool:
    """Evaluate a numeric state condition."""
    entity_id = condition.get("entity_id")
    if not entity_id:
        return False

    state = hass.states.get(entity_id)
    if state is None:
        return False

    attribute = condition.get("attribute")
    if attribute:
        value = state.attributes.get(attribute)
    else:
        value = state.state

    try:
        value = float(value)
    except (ValueError, TypeError):
        return False

    above = condition.get("above")
    below = condition.get("below")

    if above is not None and value <= float(above):
        return False
    if below is not None and value >= float(below):
        return False

    return True


def _eval_time_condition(hass: HomeAssistant, condition: dict[str, Any]) -> bool:
    """Evaluate a time condition."""
    now = datetime.now().time()

    after_str = condition.get("after")
    before_str = condition.get("before")

    after = _parse_time(after_str) if after_str else None
    before = _parse_time(before_str) if before_str else None

    if after and before:
        if after <= before:
            # Normal range (e.g. 08:00 - 22:00)
            return after <= now <= before
        else:
            # Overnight range (e.g. 22:00 - 06:00)
            return now >= after or now <= before

    if after:
        return now >= after
    if before:
        return now <= before

    return True


def _parse_time(time_str: str) -> time:
    """Parse a time string (HH:MM or HH:MM:SS)."""
    parts = time_str.split(":")
    if len(parts) == 2:
        return time(int(parts[0]), int(parts[1]))
    return time(int(parts[0]), int(parts[1]), int(parts[2]))


def _eval_template_condition(hass: HomeAssistant, condition: dict[str, Any]) -> bool:
    """Evaluate a template condition."""
    value_template = condition.get("value_template")
    if not value_template:
        return False

    tpl = Template(value_template, hass)
    tpl.hass = hass
    result = tpl.async_render()

    return str(result).lower() in ("true", "1", "yes", "on")


def _eval_or_condition(hass: HomeAssistant, condition: dict[str, Any]) -> bool:
    """Evaluate an OR condition group."""
    conditions = condition.get("conditions", [])
    return any(_evaluate_single_condition(hass, c) for c in conditions)


def _eval_and_condition(hass: HomeAssistant, condition: dict[str, Any]) -> bool:
    """Evaluate an AND condition group."""
    conditions = condition.get("conditions", [])
    return all(_evaluate_single_condition(hass, c) for c in conditions)


def _eval_not_condition(hass: HomeAssistant, condition: dict[str, Any]) -> bool:
    """Evaluate a NOT condition group."""
    conditions = condition.get("conditions", [])
    return not any(_evaluate_single_condition(hass, c) for c in conditions)
