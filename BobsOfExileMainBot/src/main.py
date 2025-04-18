"""

Requirements:
- discord
- psutil
- typeshed_client
Requirements Dev:
- types-psutil
- black
- mypy

IMPORTANT!
The host commands are only supported on LINUX devices (currently only tested un Ubuntu)
DANGER!
It's not recommended to run bot this unless you absolutely know how it functions
This is a very experimental scenario where the commands can control the host OS
You have been warned
DANGER!
This project provides MINIMAL protection by encoding the token in base85 instead of plain text
However base85 is ALMOST plain text (almost everyone knows how to convert it back)

Notes:
- In order to reset the saved token - delete the TOKEN.txt file
"""

# TODO:
# Shutdown OS (most important command)
# - Problems with permissions
# - Cross-compatibility
# - Cancelling
# TODO:
# IM NOT EVEN USING THE ADD CONTEXT FUNCTION
# TODO:
# Make some commands linux-only, maybe upgrade the register handlers again


import logging
import discord
from discord.ext import commands
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
    LOGS_ENABLE_DISCORD_MODULE,
)
from async_helpers import synchronize_run
from COMMANDS_REGISTERS import COMMANDS
from logs import ldbg
from tokens import handle_token, get_logs_adjusted_token_text
from bot import get_correct_intents, start_bot
from commands_helpers import register_commands
from events_helpers import register_events
from EVENTS_REGISTERS import EVENTS_REGISTER


def main() -> None:
    if not LOGS_ENABLE_DISCORD_MODULE:
        ldbg("Disabling discord module logs")
        logging.basicConfig(level=logging.FATAL)
        logging.getLogger("discord").setLevel(logging.FATAL)
        logging.getLogger("aiohttp").setLevel(logging.FATAL)

    token: str = handle_token()

    token_text: str = get_logs_adjusted_token_text(token)
    logs_infix: str = f"{token_text=}{s}"
    ldbg(f"{logs_infix}Proceeding with token")

    intents: discord.Intents = get_correct_intents()
    bot: commands.Bot = commands.Bot(command_prefix="!", intents=intents)

    ldbg("Registering commands")
    register_commands(bot, COMMANDS)
    ldbg("Registering events")
    register_events(bot, EVENTS_REGISTER)

    ldbg("Starting bot")
    synchronize_run(start_bot(bot, token))


if __name__ == "__main__":
    main()
