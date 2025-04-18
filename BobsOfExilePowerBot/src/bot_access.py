from common import AccessInfo, BotContext
from logs import ldbg


# THIS IS UNUSED BECAUSE APPARENTLY PARAMSPECS MAKE DISCORD.PY CONFUSED (learnt it the hard way)
# from typing import Callable, Concatenate, Coroutine, Any
# def wrap_cmd_access[**A, B](
#     cmd: Callable[Concatenate[BotContext, A], Coroutine[Any, Any, B]],
#     access: AccessInfo
# ) -> Callable[Concatenate[BotContext, A], Coroutine[Any, Any, B | None]]:
#     async def inner(ctx: BotContext, *args: A.args, **kwargs: A.kwargs) -> B | None:
#         user_id: int = ctx.author.id
#         authorized: bool = can_access(user_id, access)
#         if authorized:
#             return await cmd(ctx, *args, **kwargs)
#         else:
#             await ctx.send("Not authorized to use this command")
#             return None
#     inner.__name__ = cmd.__name__
#     return inner


async def generic_handle_access(ctx: BotContext, access: AccessInfo) -> bool:
    # This function aims to replace wrap_cmd_access
    # -> Has access
    user_id: int = ctx.author.id
    authorized: bool = can_access(user_id, access)
    if not authorized:
        ldbg(f"User {user_id} is not authorized to use the command")
        await ctx.send("Not authorized to use this command")
        return False
    ldbg(f"User {user_id} is authorized to use the command")
    return True


def can_access(user_id: int, access: AccessInfo) -> bool:
    is_whitelist: bool = access[0]
    users: tuple[int, ...] = access[1]
    is_in_users: bool = user_id in users  # prevent searching twice
    if is_whitelist and is_in_users:
        return True
    if not is_whitelist and not is_in_users:
        return True
    return False
