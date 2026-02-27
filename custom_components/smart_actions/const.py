"""Constants for Smart Actions integration."""

DOMAIN = "smart_actions"

# Config keys
CONF_ACTIONS = "actions"
CONF_ACTION_ID = "id"
CONF_ACTION_NAME = "name"
CONF_ACTION_ICON = "icon"
CONF_ACTION_COLOR = "color"
CONF_ACTION_DESCRIPTION = "description"
CONF_ACTION_CONFIRM = "confirm"
CONF_ACTION_CONDITIONS = "conditions"
CONF_ACTION_USERS = "users"
CONF_ACTION_SERVICE = "action"
CONF_ACTION_ENABLED = "enabled"
CONF_ACTION_PRIORITY = "priority"

# Defaults
DEFAULT_ICON = "mdi:lightning-bolt"
DEFAULT_COLOR = "primary"
DEFAULT_PRIORITY = 50
DEFAULT_CONFIRM = False

# Services
SERVICE_EXECUTE = "execute"
SERVICE_RELOAD = "reload"

# Attributes
ATTR_ACTION_ID = "action_id"
ATTR_ACTIONS = "actions"
ATTR_ACTIVE_COUNT = "active_count"
ATTR_USER_ID = "user_id"
ATTR_ALL_ACTIONS = "all_actions"

# Events
EVENT_ACTION_EXECUTED = f"{DOMAIN}_action_executed"
EVENT_ACTION_STATE_CHANGED = f"{DOMAIN}_action_state_changed"

# Platforms
PLATFORMS = ["binary_sensor", "sensor"]
