from typing import Callable, Any
import discord
from discord.ext import commands
from common import TupList, CmdsRegister, EventsRegister, CfgMasterOptions
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
)
from logs import get_secret_text as gs, limit_length as lm, ldbg
from cfg import get_shared_cfg, Cfg
from python_helpers import wrap_arg
from events.on_error import on_error
from events.on_command_error import on_command_error
from events.on_ready import on_ready
from commands.ping import ping
from commands.echo import echo
from commands.host_power import host_power_on, host_power_off
from commands.host_status import (
    host_print_status,
    host_print_at_code,
    host_print_wattage,
    host_print_power
)
from commands.nuke import nuke


# fmt: off
CMDS: CmdsRegister = [
    (ping, 'ping', ()),
    (echo, "echo", ("say",)),
    (host_power_on, "host-power-on", ("host-poweron", "host-pon")),
    (host_power_off, "host-power-off", ("host-poweroff", "host-poff")),
    (host_print_status, "host-print-power-raw", ("host-power-raw", "host-pwr-raw")),
    (host_print_at_code, "host-print-status-at-code", ("host-status-at-code", "host-code")),
    (host_print_wattage, "host-print-wattage", ("host-wattage", "host-watts")),
    (host_print_power, "host-print-power", ("host-power", "host-pwr")),
    (nuke, "nuke", ()) # Fun command
]
EVENTS: EventsRegister = [
    (on_error, False),
    (on_command_error, False),
    (on_ready, True)
]
# fmt: on


async def bot_login(bot: commands.Bot, token: str) -> None:
    try:
        ldbg("Logging In!")
        await bot.login(token)
    except discord.LoginFailure:
        raise RuntimeError(
            f"Token: {lm(gs(token))}This Discord bot token is incorrect! Please enter a working one!"
        )


async def bot_connect(bot: commands.Bot) -> None:
    ldbg("Connecting!")
    await bot.connect()


def setup_bot() -> commands.Bot:
    cfg: Cfg = get_shared_cfg()
    prefix: str = cfg.get_master_str_data(
        CfgMasterOptions.DISCORD_CMD_PREFIX.value, True
    )
    intents: discord.Intents = discord.Intents().default()
    intents.message_content = True
    bot: commands.Bot = commands.Bot(command_prefix=prefix, intents=intents)

    cmds: CmdsRegister = CMDS
    register_cmds(bot, cmds)
    events: EventsRegister = EVENTS
    register_events(bot, events)
    return bot


def register_cmd(
    bot: commands.Bot,
    fun: Callable[..., Any],
    name: str,
    aliases: TupList[str],
) -> None:
    logs_infix: str = f"Name: {name}{s}Aliases: {aliases}{s}Function: {fun.__name__}{s}"
    ldbg(f"{logs_infix}Registering command")
    bot.command(name=name, aliases=aliases)(fun)


def register_cmds(bot: commands.Bot, register: CmdsRegister):
    for entry in register:
        fun: Callable[..., Any] = entry[0]
        name: str = entry[1]
        aliases: TupList[str] = entry[2]
        register_cmd(bot, fun, name, aliases)


def register_event(bot: commands.Bot, event: Callable[..., Any]) -> None:
    logs_infix: str = f"Event: {event.__name__}{s}"
    ldbg(f"{logs_infix}Registering event")
    bot.event(event)


def register_events(bot: commands.Bot, register: EventsRegister):
    for event in register:
        event_func: Callable[..., Any] = event[0]
        wrap_bot_arg: bool = event[1]
        if wrap_bot_arg:
            event_func = wrap_arg(bot, event_func)
        register_event(bot, event_func)
