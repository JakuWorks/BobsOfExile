import pathlib
import os
import time
from typing import Type, TypeVar, Any

from .hardcoded import CONVENIENCE_STANDARD_NO_EXIST_ERROR_FORMAT, CONVENIENCE_STANDARD_WRONG_TYPE_ERROR_FORMAT


def get_env_or_error(key: str) -> str:
    value: str | None = os.getenv(key)
    if value is None:
        raise MissingEnvironmentVariableError(
            f"MISSING ENVIRONMENT VARIABLE {key=}! Consider adding it to your .env"
        )
    return value


def get_env_or_error_int(key: str) -> int:
    value: str = get_env_or_error(key)
    try:
        cast_: int = int(value)
    except ValueError:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Could not cast to INT. Consider editing your .env"
        )
    return cast_


def get_env_or_error_int_positive(key: str) -> int:
    value: int = get_env_or_error_int(key)
    if value <= 0:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Must not be negative! Consider editing your .env"
        )
    return value


def get_env_or_error_float(key: str) -> float:
    value: str = get_env_or_error(key)
    try:
        cast_: float = float(value)
    except ValueError:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Could not cast to FLOAT. Consider editing your .env"
        )
    return cast_


def get_env_or_error_path(key: str) -> pathlib.Path:
    value: str = get_env_or_error(key)
    try:
        cast_: pathlib.Path = pathlib.Path(value).expanduser().absolute().resolve()
    except ValueError:
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! Could not cast to PATHLIB.PATH. Consider editing your .env"
        )
    return cast_


def get_env_or_error_path_existing(key: str) -> pathlib.Path:
    value: pathlib.Path = get_env_or_error_path(key)
    if not value.exists():
        raise IncorrectEnvironmentVariableError(
            f"INCORRECT ENVIRONMENT VARIABLE {key=}! File doesn't exist! Consider editing your .env"
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
    existence_error_format: str = CONVENIENCE_STANDARD_NO_EXIST_ERROR_FORMAT,
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
    existence_error_format: str = CONVENIENCE_STANDARD_NO_EXIST_ERROR_FORMAT,
    type_error_format: str = CONVENIENCE_STANDARD_WRONG_TYPE_ERROR_FORMAT,
) -> TypeToEnsure:
    if value is None:
        raise existence_error_type(existence_error_format.format(name))
    if not isinstance(value, expected_type):
        raise type_error_type(type_error_format.format(name))
    return value