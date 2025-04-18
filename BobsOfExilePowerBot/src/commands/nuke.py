from typing import Any
from OTHER_SETTINGS import CMD_NUKE_ACCESS
from logs import lcmd
from bot_access import generic_handle_access


async def nuke(ctx: Any, *msg: str):
    """Fun command"""
    lcmd("Command triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_NUKE_ACCESS)
    if not authorized:
        return
    await ctx.send(f"Nuke outbound! :saluting_face:\nLiberation will be delivered to {' '.join(msg)}!")
