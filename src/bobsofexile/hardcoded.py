import logging
from typing import Sequence, Set
import shlex

# fmt: off

MODE_OPTION_SERVER: str = "server"
MODE_OPTION_CLIENT: str = "client"

DISCORD_REACHABILITY_TRIES: int = 20
DISCORD_REACHABILITY_INTERVAL: float = 2

LOGGING_MAX_BYTES: int = 1 * 1024 * 1024
LOGGING_BACKUP_COUNT: int = 1

LOGGING_MAIN_NAME: str = "bobsofexile-logger"
# LOGGING_MAIN_LEVEL: int = logging.INFO
LOGGING_MAIN_LEVEL: int = logging.DEBUG
LOGGING_MAIN_FILE: str = "log.log"
LOGGING_MAIN_FORMAT: str = r"[%(process)d] [%(asctime)s] [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)d] %(message)s"

LOGGING_DISCORD_LEVEL: int = logging.INFO
LOGGING_DISCORD_FILE: str = "discord.log"
LOGGING_DISCORD_FORMAT: str = r"[DISCORD] [%(asctime)s] [%(levelname)s] [%(module)s:%(funcName)s] %(message)s"

BOT_FILE_SEND_CHARS_THRESHOLD: int = 2000
BOT_FILE_SEND_FILENAME: str = "Message.txt"
BOT_RANKS_SEPARATOR: str = ","

POWER_DEVICE_STATUS_REQUEST_TIMEOUT: float = 6

POWEROFF_MINECRAFT_WAIT_TIME: int = 30
POWEROFF_WAIT_TIME_SECONDS: int = 25  # Amount of seconds that the server will wait before it cuts client's power
POWEROFF_REQUEST_TIMEOUT: float = 10
POWEROFF_MOCK: bool = False
POWEROFF_CMD: Sequence[str] = shlex.split(r"sudo shutdown now -P")
POWEROFF_SAFE_POWERON_BONUS_SECONDS: int = 20
REMOTE_POWEROFF_RETRIES: int = 5
REMOTE_POWEROFF_RETRY_INTERVAL: float = 5
INSTANT_POWEROFF_PING_TIMEOUT: float = 10
TESTPING_TIMEOUT: float = 10

NETWORK_CHECK_DOMAIN: str = "discord.com"

NETWORKING_MAX_RATE_KBPS: int = 1  # Just in case something goes horribly wrong

# Technically I could make net request and reply net codes to overlap but it's simpler to just avoid that, the integer limit is quite high
NETCODE_REQUEST_POWEROFF_SOON: int = 101
NETCODE_REPLY_POWEROFF_SOON_OK: int = 102
NETCODE_REPLY_POWEROFF_SOON_NO: int = 103

NETCODE_REQUEST_POWER_DEVICE_STATUS: int = 104
NETCODE_REPLY_POWER_DEVICE_STATUS_OK: int = 105
NETCODE_REPLY_POWER_DEVICE_STATUS_NO: int = 106

NETCODE_REQUEST_PING: int = 107
NETCODE_REPLY_PONG: int = 108

NET_HEARTBEAT_IVL_MS: int = 1000 * 10
NET_HEARTBEAT_TIMEOUT_MS: int = 1000 * 10

MINECRAFT_SERVER_VIEW_ELLIPSIS: str = "..."
MINECRAFT_STDOUT_PER_READ_MAX_BYTES: int = 1024
MINECRAFT_STATUS_CHECK_TIMEOUT_SECONDS = 4
MINECRAFT_ENTRIES_NAMES_SEPARATOR: str = ','
MINECRAFT_EMPTINESS_MONITOR_STATUS_TIMEOUT_S: float = 10

ENV_BOOL_VALUES_TRUE: Set[str] = {"true", "1", "yes"} # must be lowercase
ENV_BOOL_VALUES_FALSE: Set[str] = {"false", "0", "no"} # must be lowercase

ENV_KEY_DOTENV_PATH: str = "dotenv_path"
ENV_KEY_MODE: str = "mode"
ENV_KEY_TOKEN: str = "token"
ENV_KEY_DEFAULT_RESPONDER_DISCORD_CHANNEL_ID = "default_responder_discord_channel_id"
ENV_KEY_BOT_PREFIX: str = "bot_prefix"
ENV_KEY_BOT_STATUS: str = "bot_status"
ENV_KEY_RANK_TRUSTED_USERS: str = "rank_trusted_users"
ENV_KEY_RANK_OWNER_USERS: str = "rank_owner_users"
ENV_KEY_IDLING_MANAGER_ENABLE = 'idling_manager_enable'
ENV_KEY_IDLING_MANAGER_INTERVAL_SECONDS = 'idling_manager_interval_seconds'
ENV_KEY_NETWORKING_CLIENT_CONNECT_URL: str = "networking_client_connect_url"
ENV_KEY_NETWORKING_CLIENT_BIND_URL: str = "networking_client_bind_url"
ENV_KEY_NETWORKING_SERVER_CONNECT_URL: str = "networking_server_connect_url"
ENV_KEY_NETWORKING_SERVER_BIND_URL: str = "networking_server_bind_url"
ENV_KEY_NETWORKING_CURVE_CLIENT_PUBLICKEY: str = "networking_curve_client_publickey"
ENV_KEY_NETWORKING_CURVE_CLIENT_SECRETKEY: str = "networking_curve_client_secretkey"
ENV_KEY_NETWORKING_CURVE_SERVER_PUBLICKEY: str = "networking_curve_server_publickey"
ENV_KEY_NETWORKING_CURVE_SERVER_SECRETKEY: str = "networking_curve_server_secretkey"
ENV_KEY_TUYA_ACCESS_ID: str = "tuya_access_id"
ENV_KEY_TUYA_ACCESS_SECRET: str = "tuya_access_secret"
ENV_KEY_TUYA_REGION: str = "tuya_region"
ENV_KEY_TUYA_DEVICE_ID: str = "tuya_device_id"
ENV_KEY_MINECRAFT_INSTANCE_ENTRIES_NAMES: str = "minecraft_instance_entries_names"
ENV_KEY_MINECRAFT_COMMANDS_DEFAULT_TARGET: str = "minecraft_commands_default_target"
ENV_KEY_MINECRAFT_RAM_COUNTING_ENABLE: str = "minecraft_ram_counting_enable"
ENV_KEY_MINECRAFT_RAM_MAX_USAGE_MB: str = 'minecraft_ram_max_usage_mb'
ENV_KEY_MINECRAFT_EMPTY_CHECK_INTERVAL_S: str = "minecraft_empty_check_interval_s"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_START_EXECUTABLE: str = "minecraft_instance_entry_start_executable_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_ESTIMATED_MAX_RAM_USAGE_MB: str = "minecraft_instance_entry_estimated_max_ram_usage_mb_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STDOUT_BUFFER_MAX_BYTES: str = "minecraft_instance_entry_stdout_buffer_max_bytes_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_EMPTY_PROLONGED_MINIMUM_STREAK: str = "minecraft_instance_entry_empty_prolonged_minimum_streak_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_ENABLE_EMPTY_MONITORING: str = "minecraft_instance_entry_enable_empty_monitoring_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_HOST_FOR_STATUS_CHECK: str = "minecraft_instance_entry_host_for_status_check_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_PORT_FOR_STATUS_CHECK: str = "minecraft_instance_entry_port_for_status_check_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_KILL_BONUS_DELAY: str = "minecraft_instance_entry_stop_kill_bonus_delay_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_ON_EMPTY_PROLONGED: str = "minecraft_instance_entry_stop_on_empty_prolonged_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_TERMINATE_ATTEMPTS: str = "minecraft_instance_entry_stop_terminate_attempts_"
ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_TERMINATE_INTERVAL: str = "minecraft_instance_entry_stop_terminate_interval_"

# Some may be moved to .env later
TUYA_POWER_ON_CMD = {"commands": [{"code": "switch_1", "value": True}]}
TUYA_POWER_OFF_CMD = {"commands": [{"code": "switch_1", "value": False}]}
TUYA_RESPONSE_COMMAND_KEY_SUCCESS: str = "success"
TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_RESULT: str = "result"
TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_CODE: str = "code"
TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_VALUE: str = "value"
TUYA_RESPONSE_STATUS_KEY_SUCCESS: str = "success"
TUYA_RESPONSE_STATUS_RESULT_CODE_POWER_SWITCH: str = "switch_1"

ENV_ERROR_FORMAT_NO_EXIST: str = "Missing value of {0}"
ENV_ERROR_FORMAT_WRONG_TYPE: str = "Wrong type of {0}"
