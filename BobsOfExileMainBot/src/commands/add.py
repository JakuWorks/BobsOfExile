from common import Context
from OTHER_SETTINGS import CMD_ADD_ACCESS
from logs import lcmd
from bot_access import general_handle_access


async def add(ctx: Context, a: str, b: str) -> None:
    # Testing command
    lcmd("Command Triggered")
    authorized: bool = await general_handle_access(ctx, CMD_ADD_ACCESS)
    if not authorized:
        return
    try:
        a_num: float = float(a)
        b_num: float = float(b)
        sum: float = a_num + b_num
        await ctx.send(f"Sum: {sum}")
    except ValueError:
        await ctx.send("Your mom")
