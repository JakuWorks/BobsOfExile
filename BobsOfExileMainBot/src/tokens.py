from pathlib import Path
import getpass
import base64
import discord
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
    TOKEN_PATHS,
    TOKEN_SAVE_PATH,
    TOKEN_VISIBILITY_ENABLED,
    ENABLE_TOKEN_SAVING,
    TOKEN_VISIBILITY_REPLACEMENT,
)
from logs import ldbg, lwarn
from async_helpers import synchronize_run


def get_saved_token(path: Path) -> str:
    logs_infix: str = f"{path=}{s}"
    ldbg(f"{logs_infix}Looking for token")
    assert path.exists(), "Path must exist here!" #TODO mkdirs, no permissions handling
    with open(path, "rb") as f:
        encoded: bytes = f.read()
        try:
            decoded: bytes = base64.b85decode(encoded)
        except ValueError:
            lwarn(f"{logs_infix}COULDN'T DECODE TOKEN! SKIPPING!")
            return ""
        token: str = decoded.decode("utf-8")
        token = token.strip()
        token_text: str = get_logs_adjusted_token_text(token)
        token_infix: str = f"{token_text=}{s}"
        ldbg(f"{logs_infix}{token_infix}Found token")
        return token


def save_token(token: str, path: Path) -> None:
    logs_infix: str = f"{path=}{s}"
    ldbg(f"{logs_infix}Saving token")
    with open(path, "wb") as f:
        token_bytes: bytes = token.encode("utf-8")
        encoded: bytes = base64.b85encode(token_bytes)
        f.write(encoded)


async def check_token(token: str) -> bool:
    token_t: str = get_logs_adjusted_token_text(token)
    logs_infix: str = f"{token_t=}{s}"
    ldbg(f"{logs_infix}Checking token for correctness")
    intents: discord.Intents = discord.Intents.default()
    correct: bool = True
    try:
        async with discord.Client(intents=intents) as client:
            await client.login(token)
    except discord.LoginFailure:
        correct = False
    finally:
        return correct


def handle_saved_token(path: Path) -> str:
    token: str = get_saved_token(path)
    if token == "":
        return ""
    correct: bool = synchronize_run(check_token(token))
    logs_infix: str = f"{path=}{s}"
    if correct:
        ldbg(f"{logs_infix}Token is correct")
        return token

    lwarn(f"{logs_infix}Token is incorrect")
    return ""


def get_token_input() -> str:
    prompt: str
    if TOKEN_VISIBILITY_ENABLED:
        prompt = "Please enter the token: "
        return input(prompt)
    else:
        prompt = "Please enter the token (your input is invisible for security): "
        return getpass.getpass(prompt)


def handle_token_inputting() -> str:
    while True:
        token: str = get_token_input().strip()
        correct = synchronize_run(check_token(token))
        if correct:
            ldbg("The input token is Valid!")
            break
        else:
            ldbg("The input token is Invalid! Please retry")
    return token


def handle_token() -> str:
    for path in TOKEN_PATHS:
        exists = path.exists()
        logs_infix: str = f"{path=}{s}"
        if exists:
            ldbg(f"{logs_infix}Found token file")
            saved_token: str = handle_saved_token(path)
            if saved_token:
                return saved_token
        else:
            ldbg(f"{logs_infix}Didn't find token file")

    token: str = handle_token_inputting()
    if ENABLE_TOKEN_SAVING:
        save_token(token, TOKEN_SAVE_PATH)
    return token


def get_logs_adjusted_token_text(token: str) -> str:
    if TOKEN_VISIBILITY_ENABLED:
        return token
    return TOKEN_VISIBILITY_REPLACEMENT
