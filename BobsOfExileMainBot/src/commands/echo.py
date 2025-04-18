from common import Context
from OTHER_SETTINGS import CMD_ECHO_ACCESS
from bot_access import general_handle_access
from logs import lcmd


async def echo(ctx: Context, *msg: str) -> None:
    # Testing command
    lcmd("Command Triggered")
    authorized: bool = await general_handle_access(ctx, CMD_ECHO_ACCESS)
    if not authorized:
        return
    m: str = ' '.join(msg)
    await ctx.send(f"{m}")
