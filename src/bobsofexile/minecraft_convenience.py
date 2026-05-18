from typing import TypedDict, Required, TypeVar, Any
from typing_extensions import ReadOnly
from collections.abc import Sequence, MutableSequence
import pathlib
from .main_convenience import (
    get_env_or_error,
    MissingEnvironmentVariableError,
    get_env_or_error_int_positive,
    get_env_or_error_path_existing,
    IncorrectEnvironmentVariableError,
    get_env_or_error_float_positive,
    get_env_or_error_bool,
    get_env_or_error_int,
)
import logging

T = TypeVar("T")

from .hardcoded import (
    ENV_KEY_MINECRAFT_INSTANCE_ENTRIES_NAMES,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_EMPTY_PROLONGED_MINIMUM_STREAK,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_ENABLE_EMPTY_MONITORING,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_ESTIMATED_MAX_RAM_USAGE_MB,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STATUS_CHECK_HOST,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STATUS_CHECK_PORT,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STATUS_CHECK_PROTOCOL_VERSION,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_START_EXECUTABLE,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STDOUT_BUFFER_MAX_BYTES,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_KILL_BONUS_DELAY,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_ON_EMPTY_PROLONGED,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_TERMINATE_ATTEMPTS,
    ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_TERMINATE_INTERVAL,
    MINECRAFT_ENTRIES_NAMES_SEPARATOR,
)


class MinecraftEntryConfigFromEnv(TypedDict):
    name: ReadOnly[Required[str]]
    start_executable: ReadOnly[Required[pathlib.Path]]
    estimated_max_ram_usage_mb: ReadOnly[Required[int]]
    stdout_buffer_max_bytes: ReadOnly[Required[int]]
    empty_prolonged_minimum_streak: ReadOnly[Required[int]]
    enable_empty_monitoring: ReadOnly[Required[bool]]
    status_check_host: ReadOnly[Required[str]]
    status_check_port: ReadOnly[Required[int]]
    status_check_protocol_version: ReadOnly[Required[int]]
    stop_kill_bonus_delay: ReadOnly[Required[float]]
    stop_on_empty_prolonged: ReadOnly[Required[bool]]
    stop_terminate_attempts: ReadOnly[Required[int]]
    stop_terminate_interval: ReadOnly[Required[float]]


def get_minecraft_entry_env_config_str(key: str, missing_format: str) -> str | None:
    try:
        return get_env_or_error(key)
    except MissingEnvironmentVariableError:
        logging.warning(missing_format.format(key))


def get_minecraft_entry_env_config_bool(
    key: str, missing_format: str, wrong_type_format: str
) -> bool | None:
    try:
        return get_env_or_error_bool(key)
    except MissingEnvironmentVariableError:
        logging.warning(missing_format.format(key))
    except IncorrectEnvironmentVariableError:
        logging.warning(wrong_type_format.format(key, "a boolean"))


def get_minecraft_entry_env_config_int(
    key: str, missing_format: str, wrong_type_format: str
) -> int | None:
    try:
        return get_env_or_error_int(key)
    except MissingEnvironmentVariableError:
        logging.warning(missing_format.format(key))
    except IncorrectEnvironmentVariableError:
        logging.warning(wrong_type_format.format(key, "an int"))


def get_minecraft_entry_env_config_int_positive(
    key: str, missing_format: str, wrong_type_format: str
) -> int | None:
    try:
        return get_env_or_error_int_positive(key)
    except MissingEnvironmentVariableError:
        logging.warning(missing_format.format(key))
    except IncorrectEnvironmentVariableError:
        logging.warning(wrong_type_format.format(key, "a positive int"))


def get_minecraft_entry_env_config_float_positive(
    key: str, missing_format: str, wrong_type_format: str
) -> float | None:
    try:
        return get_env_or_error_float_positive(key)
    except MissingEnvironmentVariableError:
        logging.warning(missing_format.format(key))
    except IncorrectEnvironmentVariableError:
        logging.warning(wrong_type_format.format(key, "a positive float"))


def get_minecraft_entry_env_config_path_existing(
    key: str, missing_format: str, wrong_type_format: str
) -> pathlib.Path | None:
    try:
        return get_env_or_error_path_existing(key)
    except MissingEnvironmentVariableError:
        logging.warning(missing_format.format(key))
    except IncorrectEnvironmentVariableError:
        logging.warning(wrong_type_format.format(key, "an existing path"))


def collect_minecraft_entry_config_from_env(
    name: str,
) -> MinecraftEntryConfigFromEnv | None:
    missing_format: str = (
        f"Tried collecting the minecraft entry with name '{name}' but there is no value under key"
        " '{}'"
    )
    wrong_type_format: str = (
        f"Tried collecting the minecraft entry with name '{name}' but the value under key"
        + " '{}' has the wrong type (must be {})"
    )

    all_values: MutableSequence[Any] = []

    # fmt: off
    start_executable: pathlib.Path | None = get_minecraft_entry_env_config_path_existing(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_START_EXECUTABLE + name, missing_format, wrong_type_format,)
    all_values.append(start_executable)
    estimated_max_ram_usage_mb: int | None = get_minecraft_entry_env_config_int_positive(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_ESTIMATED_MAX_RAM_USAGE_MB + name, missing_format, wrong_type_format)
    all_values.append(estimated_max_ram_usage_mb)
    stdout_buffer_max_bytes: int | None = get_minecraft_entry_env_config_int_positive(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STDOUT_BUFFER_MAX_BYTES + name, missing_format, wrong_type_format)
    all_values.append(stdout_buffer_max_bytes)
    empty_prolonged_minimum_streak: int | None = get_minecraft_entry_env_config_int_positive(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_EMPTY_PROLONGED_MINIMUM_STREAK + name, missing_format, wrong_type_format)
    all_values.append(empty_prolonged_minimum_streak)
    enable_empty_monitoring: bool | None = get_minecraft_entry_env_config_bool(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_ENABLE_EMPTY_MONITORING + name, missing_format, wrong_type_format)
    all_values.append(enable_empty_monitoring)
    status_check_host: str | None = get_minecraft_entry_env_config_str(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STATUS_CHECK_HOST + name, missing_format)
    all_values.append(status_check_host)
    status_check_port: int | None = get_minecraft_entry_env_config_int_positive(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STATUS_CHECK_PORT + name, missing_format, wrong_type_format)
    all_values.append(status_check_port)
    status_check_protocol_version: int | None = get_minecraft_entry_env_config_int(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STATUS_CHECK_PROTOCOL_VERSION + name, missing_format, wrong_type_format)
    all_values.append(status_check_protocol_version)
    stop_kill_bonus_delay: float | None = get_minecraft_entry_env_config_float_positive(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_KILL_BONUS_DELAY + name, missing_format, wrong_type_format)
    all_values.append(stop_kill_bonus_delay)
    stop_on_empty_prolonged: bool | None = get_minecraft_entry_env_config_bool(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_ON_EMPTY_PROLONGED + name, missing_format, wrong_type_format)
    all_values.append(stop_on_empty_prolonged)
    stop_terminate_attempts: int | None = get_minecraft_entry_env_config_int_positive(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_TERMINATE_ATTEMPTS + name, missing_format, wrong_type_format)
    all_values.append(stop_terminate_attempts)
    stop_terminate_interval: float | None = get_minecraft_entry_env_config_float_positive(ENV_KEY_MINECRAFT_INSTANCE_ENTRY_PREFIX_STOP_TERMINATE_INTERVAL + name, missing_format, wrong_type_format)
    all_values.append(stop_terminate_interval)
    # fmt: on

    # This way all warnings will be printed before exiting

    if None in all_values:
        return None

    # My type checker doesn't infer that the values are guaranteed to be None now
    assert start_executable is not None
    assert estimated_max_ram_usage_mb is not None
    assert stdout_buffer_max_bytes is not None
    assert empty_prolonged_minimum_streak is not None
    assert enable_empty_monitoring is not None
    assert status_check_host is not None
    assert status_check_port is not None
    assert status_check_protocol_version is not None
    assert stop_kill_bonus_delay is not None
    assert stop_on_empty_prolonged is not None
    assert stop_terminate_attempts is not None
    assert stop_terminate_interval is not None

    return MinecraftEntryConfigFromEnv(
        name=name,
        start_executable=start_executable,
        estimated_max_ram_usage_mb=estimated_max_ram_usage_mb,
        stdout_buffer_max_bytes=stdout_buffer_max_bytes,
        status_check_host=status_check_host,
        status_check_port=status_check_port,
        status_check_protocol_version=status_check_protocol_version,
        empty_prolonged_minimum_streak=empty_prolonged_minimum_streak,
        stop_terminate_attempts=stop_terminate_attempts,
        stop_terminate_interval=stop_terminate_interval,
        stop_kill_bonus_delay=stop_kill_bonus_delay,
        enable_empty_monitoring=enable_empty_monitoring,
        stop_on_empty_prolonged=stop_on_empty_prolonged,
    )


def collect_minecraft_entry_configs_from_env() -> Sequence[MinecraftEntryConfigFromEnv]:
    names_value: str = get_env_or_error(ENV_KEY_MINECRAFT_INSTANCE_ENTRIES_NAMES)
    names: Sequence[str] = names_value.split(MINECRAFT_ENTRIES_NAMES_SEPARATOR)
    env_configs: MutableSequence[MinecraftEntryConfigFromEnv] = list()
    for name in names:
        env_config: MinecraftEntryConfigFromEnv | None = (
            collect_minecraft_entry_config_from_env(name)
        )
        if env_config is not None:
            env_configs.append(env_config)
    return env_configs
