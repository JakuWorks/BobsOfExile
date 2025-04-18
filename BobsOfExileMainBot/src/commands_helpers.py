from typing import Collection
from common import CommandsRegister, Platform, SimpleCommand, CommandInfo
from discord.ext import commands
from logs import ldbg
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
)
from platforms import get_platform

# MADE CHANGES


def register_command(bot: commands.Bot, command: CommandInfo) -> None:
    # Assumes the command is "registerable"
    name: str = command[1]
    aliases: Collection[str] = command[2]
    func: SimpleCommand = command[4]
    bot.command(name=name, aliases=aliases)(func)

    aliases_t: str = ' '.join(aliases)
    func_t: str = func.__name__
    logs_infix: str = f"{name=}{s}{aliases_t=}{s}{func_t=}{s}"
    ldbg(f"{logs_infix}Cmd Registered")


def think_register_command(bot: commands.Bot, command: CommandInfo) -> None:
    enabled: bool = command[0]
    if not enabled:
        name: str = command[1]
        logs_infix: str = f"{name=}{s}"
        ldbg(f"{logs_infix}Cmd not registered - not enabled")
        return
    supported: Collection[Platform] = command[3]
    plat: Platform = get_platform()  # get_platform caches its results
    if plat not in supported:
        name: str = command[1]
        logs_infix: str = f"{name=}{s}"
        ldbg(f"{logs_infix}Cmd not registered - platform not supported")
        return
    register_command(bot, command)


def register_commands(bot: commands.Bot, commands: CommandsRegister) -> None:
    for info in commands:
        think_register_command(bot, info)
