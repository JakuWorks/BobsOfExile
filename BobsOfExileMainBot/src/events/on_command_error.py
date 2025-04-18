from common import Any
from logs import levent, ldbg
from discord.ext import commands


async def on_command_error(
    *args: Any, **kwargs: Any
) -> None:
    levent("GOT A COMMAND ERROR!")
    # The arguments that discord gives you are so weird
    # It's just better to do this instead
    for arg in args:
        if isinstance(arg, commands.CommandInvokeError):
            raise arg.original
        if isinstance(arg, commands.CommandNotFound):
            ldbg("Command not found")
            break
