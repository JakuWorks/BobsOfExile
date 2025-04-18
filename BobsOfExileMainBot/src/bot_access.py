from common import AccessInfo, BotContext
from logs import ldbg
from OTHER_SETTINGS import LOGS_SEPARATOR as s


async def general_handle_access(ctx: BotContext, access: AccessInfo) -> bool:
    # -> has access
    user_id: int = ctx.author.id
    authorized: bool = can_access(user_id, access)
    logs_infix: str = f"{user_id=}{s}"
    if not authorized:
        ldbg(f"{logs_infix}Not authorized to use the command")
        await ctx.send("Not authorized to use this command")
        return False
    ldbg(f"{logs_infix}Not authorized to use the command")
    return True


def can_access(user_id: int, access: AccessInfo) -> bool:
    is_whitelist: bool = access[0]
    users: tuple[int, ...] = access[1]
    is_in_users: bool = user_id in users
    if is_whitelist and is_in_users:
        return True
    if not is_whitelist and not is_in_users:
        return True
    return False
