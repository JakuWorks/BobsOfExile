from typing import Any, Callable
from common import EventsRegister, EventEntry
from logs import ldbg
from discord.ext import commands
from python_helpers import wrap_arg
from OTHER_SETTINGS import LOGS_SEPARATOR as s


def register_event(bot: commands.Bot, event: EventEntry) -> None:
    e: Callable[..., Any] = event[0]
    need_bot_context: bool = event[1]
    if need_bot_context:
        bot.event(wrap_arg(bot, e))
    else:
        bot.event(e)
    name: str = e.__name__
    logs_infix: str = f"{name=}{s}"
    ldbg(f"{logs_infix}Event Registered")



def register_events(
    bot: commands.Bot,
    register: EventsRegister,
) -> None:
    ldbg("Registering events")
    for event in register:
        register_event(bot, event)
