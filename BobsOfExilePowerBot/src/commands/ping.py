from common import BotContext
from OTHER_SETTINGS import CMD_PING_ACCESS
from logs import lcmd
from bot_access import generic_handle_access


async def ping(ctx: BotContext) -> None:
    """Ping Pong"""
    # Testing command
    lcmd("Command Triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_PING_ACCESS)
    if not authorized:
        return
    await ctx.send("Pong!")
