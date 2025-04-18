from common import Context
from OTHER_SETTINGS import CMD_HI_ACCESS
from logs import lcmd
from bot_access import general_handle_access


async def hi(ctx: Context) -> None:
    # Testing command
    lcmd("Command Triggered")
    authorized: bool = await general_handle_access(ctx, CMD_HI_ACCESS)
    if not authorized:
        return
    await ctx.send("Sup")
