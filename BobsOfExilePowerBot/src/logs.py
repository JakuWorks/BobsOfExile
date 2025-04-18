from OTHER_SETTINGS import (
    LOGS_SECRETS_PRINT,
    LOGS_SECRETS_REPLACEMENT,
    LOGS_SEPARATOR as s,
    LOGS_INFO_ENABLED,
    LOGS_INFO_PREFIX,
    LOGS_DBG_PREFIX,
    LOGS_WARN_PREFIX,
    LOGS_DBG_ENABLED,
    LOGS_WARN_ENABLED,
    LOGS_CMD_ENABLED,
    LOGS_CMD_PREFIX,
    LOGS_EVENT_ENABLED,
    LOGS_EVENT_PREFIX,
)
from python_helpers import get_caller


def limit_length(text: str, maxl: int = 6, ending: str = "...") -> str:
    l: int = len(text)
    endl: int = len(ending)
    if l <= maxl:
        return text
    new_textl: int = maxl - endl
    new_text: str = text[:new_textl]
    return f"{new_text}{ending}"


def get_secret_text(secret: str) -> str:
    if LOGS_SECRETS_PRINT:
        return secret
    return LOGS_SECRETS_REPLACEMENT


# BLATANTLY TAKEN FROM ONE OF MY OTHER PROJECTS ('BobsOfExileBot')
def generic_log(message: str, prefix: str, necessary_go_backs: int) -> None:
    caller_infix: str
    try:
        caller: str = get_caller(necessary_go_backs)
        caller_infix = f"{s}{caller}{s}"
    except RuntimeError:
        caller_infix = ""
    full: str = f"{prefix}{caller_infix}{message}"
    print(full)


def linfo(message: str) -> None:
    if LOGS_INFO_ENABLED:
        generic_log(message, LOGS_INFO_PREFIX, 3)


def ldbg(message: str) -> None:
    if LOGS_DBG_ENABLED:
        generic_log(message, LOGS_DBG_PREFIX, 3)


def lwarn(message: str) -> None:
    if LOGS_WARN_ENABLED:
        generic_log(message, LOGS_WARN_PREFIX, 3)


def lcmd(message: str) -> None:
    if LOGS_CMD_ENABLED:
        generic_log(message, LOGS_CMD_PREFIX, 3)


def levent(message: str) -> None:
    if LOGS_EVENT_ENABLED:
        generic_log(message, LOGS_EVENT_PREFIX, 3)
