from typing import Any, cast

from homeassistant.core import HomeAssistant

from homeassistant.helpers.condition import (
    async_from_config,
)

from homeassistant.helpers.config_validation import CONDITION_SCHEMA
from homeassistant.helpers.template import Template


async def _build_condition_tests(self):
    for action in self._actions.values():
        if action.conditions:
            try:
                # Hydrate any template strings first
                hydrated = conditions_from_json(self.hass, action.conditions)
                tests = []
                for cond_conf in hydrated:
                    test = await async_from_config(self.hass, cond_conf)
                    tests.append(test)
                action._condition_tests = tests
            except Exception:
                # _LOGGER.exception("Invalid conditions for %s", action.id)
                print("Invalid conditions for %s", action.id)
                action._condition_tests = None


def conditions_to_json(conditions: list[dict]) -> list[dict]:
    """Convert validated condition configs to JSON-safe dicts."""
    result = []
    for cond in conditions:
        result.append(_serialize_condition(cond))
    return result


def _serialize_condition(cond) -> dict:
    """Recursively serialize a condition dict, converting Templates to strings."""
    if isinstance(cond, Template):
        # the raw template string
        return cond.template  # pyright: ignore[reportReturnType]

    if isinstance(cond, list):
        return [_serialize_condition(item) for item in cond]  # pyright: ignore[reportReturnType]

    if isinstance(cond, dict):
        return {key: _serialize_condition(value) for key, value in cond.items()}

    return cond


def conditions_from_json(hass: HomeAssistant, conditions: list[dict]) -> list[dict]:
    """Convert stored condition dicts back, re-hydrating Template objects."""
    result = []
    for cond in conditions:
        result.append(_deserialize_condition(hass, cond))
    return result


def _deserialize_condition(hass: HomeAssistant, cond):
    """Recursively restore Template objects in condition dicts."""
    if isinstance(cond, list):
        return [_deserialize_condition(hass, item) for item in cond]

    if isinstance(cond, dict):
        result = {}
        for key, value in cond.items():
            if key in ("value_template",) and isinstance(value, str):
                tpl = Template(value, hass)
                tpl.hass = hass
                result[key] = tpl
            else:
                result[key] = _deserialize_condition(hass, value)
        return result

    return cond
