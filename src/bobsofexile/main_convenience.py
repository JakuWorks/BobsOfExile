import pathlib
import os


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
