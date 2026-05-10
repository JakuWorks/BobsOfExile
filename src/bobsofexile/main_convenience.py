import pathlib
import os
import time
from collections.abc import Sequence
from typing import Type, TypeVar, Any

from .hardcoded import (
    ENV_ERROR_FORMAT_NO_EXIST,
    ENV_ERROR_FORMAT_WRONG_TYPE,
    ENV_BOOL_VALUES_TRUE,
    ENV_BOOL_VALUES_FALSE,
)


def get_env_or_error(key: str) -> str:
    value: str | None = os.getenv(key)
    if value is None:
        raise MissingEnvironmentVariableError(
            f"MISSING ENVIRONMENT VARIABLE {key=}! Consider adding it to your .env"
        )
    return value


def get_env_or_error_bool(key: str) -> bool:
    value: str = get_env_or_error(key)
    value = value.lower()

    if value in ENV_BOOL_VALUES_TRUE:
        return True
    if value in ENV_BOOL_VALUES_FALSE:
        return False
    raise IncorrectEnvironmentVariableError(
        f"INCORRECT ENVIRONMENT VARIABLE {key=}! Could not understand as BOOL ({value=}). Consider editing your .env"
    )


def get_env_or_error_int(key: str) -> int:
    value: str = get_env_or_error(key)
    try:
        cast_: int = int(value)
    except ValueError:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Could not cast to INT ({value=}). Consider editing your .env"
        )
    return cast_


def get_env_or_error_int_positive(key: str) -> int:
    value: int = get_env_or_error_int(key)
    if value <= 0:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Must not be negative ({value=})! Consider editing your .env"
        )
    return value


def get_env_or_error_float(key: str) -> float:
    value: str = get_env_or_error(key)
    try:
        cast_: float = float(value)
    except ValueError:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Could not cast to FLOAT ({value=}). Consider editing your .env"
        )
    return cast_


def get_env_or_error_float_positive(key: str) -> float:
    value: float = get_env_or_error_float(key)
    if value <= 0:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Must not be negative ({value=})! Consider editing your .env"
        )
    return value


def get_env_or_error_path(key: str) -> pathlib.Path:
    value: str = get_env_or_error(key)
    try:
        cast_: pathlib.Path = pathlib.Path(value).expanduser().absolute().resolve()
    except ValueError:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Could not cast to PATHLIB.PATH ({value=}). Consider editing your .env"
        )
    return cast_


def get_env_or_error_path_existing(key: str) -> pathlib.Path:
    value: pathlib.Path = get_env_or_error_path(key)
    if not value.exists():
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! File doesn't exist ({value=})! Consider editing your .env"
        )
    return value


class EnvironmentVariableError(Exception):
    pass


class MissingEnvironmentVariableError(EnvironmentVariableError):
    pass


class IncorrectEnvironmentVariableError(EnvironmentVariableError):
    pass


def get_future_time(after_seconds: float) -> float:
    return time.time() + after_seconds


def ensure_existence(
    name: str,
    value: Any,
    existence_error_type: Type[Exception],
    existence_error_format: str = ENV_ERROR_FORMAT_NO_EXIST,
) -> Any:
    if value is None:
        raise existence_error_type(existence_error_format.format(name))
    return value


TypeToEnsure = TypeVar("TypeToEnsure", covariant=False, contravariant=False)


def ensure_existence_and_type(
    name: str,
    expected_type: Type[TypeToEnsure],
    value: Any,
    existence_error_type: Type[Exception],
    type_error_type: Type[Exception],
    existence_error_format: str = ENV_ERROR_FORMAT_NO_EXIST,
    type_error_format: str = ENV_ERROR_FORMAT_WRONG_TYPE,
) -> TypeToEnsure:
    if value is None:
        raise existence_error_type(existence_error_format.format(name))
    if not isinstance(value, expected_type):
        raise type_error_type(type_error_format.format(name))
    return value


def bytes_as_text(
    bytes_: bytes,
    start: int | None = None,
    stop: int | None = None,
    step: int | None = None,
    errors_decoding_mode: str = "replace",
) -> str:
    slice_as_bytes: bytes = bytes(bytes_)[start:stop:step]
    return slice_as_bytes.decode(errors=errors_decoding_mode)


def bytes_as_lines(
    bytes_: bytes,
    max_lines: int,
    errors_decoding_mode: str = "replace",
) -> Sequence[str]:
    # This is an extremely lazy way of doing this and will waste resources
    as_text: str = bytes_as_text(
        bytes_=bytes_,
        start=None,
        stop=None,
        step=None,
        errors_decoding_mode=errors_decoding_mode,
    )
    lines: Sequence[str] = as_text.split("\n")
    lines_l: int = len(lines)
    start_index: int = max(0, lines_l - max_lines)
    return lines[start_index:]


def bytes_as_lines_length_limited(
    bytes_: bytes,
    max_lines: int,
    max_line_length: int,
    ellipsis: str = "...",
    errors_decoding_mode: str = "replace",
) -> Sequence[str]:
    ellipsis = ellipsis[:max_line_length]
    as_lines: Sequence[str] = bytes_as_lines(
        bytes_=bytes_, max_lines=max_lines, errors_decoding_mode=errors_decoding_mode
    )
    lines: Sequence[str] = list()
    ellipsis_l: int = len(ellipsis)
    max_length_with_ellipsis: int = max(0, max_line_length - ellipsis_l)
    for line in as_lines:
        line_l: int = len(line)
        if line_l > max_line_length:
            new_line: str = line[:max_length_with_ellipsis] + ellipsis
            lines.append(new_line)
            continue
        lines.append(line)
    return lines
