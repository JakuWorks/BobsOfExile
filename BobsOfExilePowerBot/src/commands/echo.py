from common import BotContext
from OTHER_SETTINGS import CMD_ECHO_ACCESS
from logs import lcmd
from bot_access import generic_handle_access


async def echo(ctx: BotContext, *msg: str) -> None:
    """Repeats what you say. Usage: echo MESSAGE"""
    # Testing command
    lcmd("Command Triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_ECHO_ACCESS)
    if not authorized:
        return
    await ctx.send(" ".join(msg))
