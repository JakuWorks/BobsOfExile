from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
    LOGS_DEBUG_ENABLED,
    LOGS_DEBUG_PREFIX,
    LOGS_CMD_ENABLED,
    LOGS_CMD_PREFIX,
    LOGS_WARN_ENABLED,
    LOGS_WARN_PREFIX,
    LOGS_EVENT_ENABLED,
    LOGS_EVENT_PREFIX,
)
from python_helpers import get_caller



def general_log(message: str, prefix: str, necessary_go_backs: int) -> None:
    caller_infix: str
    try:
        caller: str = get_caller(necessary_go_backs)
        caller_infix = f"{caller}{s}"
    except RuntimeError:
        caller_infix = ""
    full: str = f"{prefix}{caller_infix}{message}"
    print(full)


def ldbg(message: str) -> None:
    if LOGS_DEBUG_ENABLED:
        general_log(message, LOGS_DEBUG_PREFIX, 3)


def lcmd(message: str) -> None:
    if LOGS_CMD_ENABLED:
        general_log(message, LOGS_CMD_PREFIX, 3)


def levent(message: str) -> None:
    if LOGS_EVENT_ENABLED:
        general_log(message, LOGS_EVENT_PREFIX, 3)


def lwarn(message: str) -> None:
    if LOGS_WARN_ENABLED:
        general_log(message, LOGS_WARN_PREFIX, 3)