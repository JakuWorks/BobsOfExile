from typing import Callable, Coroutine, Any, ParamSpec, Concatenate
from types import CoroutineType
from functools import wraps
import logging

from .commands import CallContext
from .permissions import PermissionContext
from .discord_convenience import respond_text_or_file_from_call_context as respond

import asyncclick as click

P = ParamSpec("P")


def simple_check_permissions(call_context: CallContext) -> bool:
    """-> has_permission"""
    permission_context: PermissionContext = PermissionContext(
        user_id=str(call_context.young.message_context.author.id)
    )
    return call_context.old.permission_resolver.check_access(permission_context)


async def simple_handle_permissions(call_context: CallContext) -> bool:
    """-> has_permission
    Writes permission info and exists
    """
    has_permission: bool = simple_check_permissions(call_context)
    if not has_permission:
        await respond(
            call_context,
            f"Insufficient permissions to access this command. Requires: {call_context.old.permission_resolver.description}",
        )
    return has_permission


async def simple_handle_lock_request(call_context: CallContext) -> bool:
    """-> Is_locked"""
    if not call_context.young.respect_command_lock:
        return False
    if not call_context.grand.commands_lock.locked():
        await call_context.grand.commands_lock.acquire()
        return False
    await respond(
        call_context,
        content="An another command is currently in progress. Please try again later.",
    )
    return True


async def simple_handle_lock_release(call_context: CallContext) -> None:
    # Doesn't need to be async but it may be useful later
    if not call_context.young.respect_command_lock:
        return
    call_context.grand.commands_lock.release()


async def simple_error_response(call_context: CallContext, error: Exception) -> None:
    await respond(call_context, f"Command failed due to an error:\n```{repr(error)}```")


def simple_wrap_command_call(
    cmd: Callable[Concatenate[CallContext, P], Coroutine[Any, Any, None]], respect_lock: bool
) -> "Callable[Concatenate[click.Context, P], CoroutineType[Any, Any, None]]":
    # CoroutineType is not subscriptable ??? The quotes avoid this
    raw_name: str = cmd.__name__
    wrapped_name: str = f"wrapped_{raw_name}"

    @wraps(cmd)
    async def wrapped(ctx: click.Context, *args: P.args, **kwargs: P.kwargs) -> None:
        logging.info(f"Calling wrapped command | {wrapped_name}")
        call_context: CallContext = ctx.obj

        if not await simple_handle_permissions(call_context):
            return

        if respect_lock and await simple_handle_lock_request(call_context):
            logging.info(f"Failed to acquire command lock | {wrapped_name}")
            return

        logging.info(f"Acquired command lock | {wrapped_name}")

        logging.info(f"Calling raw command | {raw_name}")
        try:
            await cmd(call_context, *args, **kwargs)
        except Exception as e:
            logging.info(
                f"Releasing command lock due to an exception and re-raising! | {wrapped_name}",
                exc_info=e,
            )
            await simple_error_response(call_context, e)
            await simple_handle_lock_release(call_context)
            raise

        logging.info(f"Releasing command lock {wrapped_name}")
        if respect_lock:
            await simple_handle_lock_release(call_context)

    # Changing this name does NOT change the displayed inside logging
    wrapped.__name__ = wrapped_name
    return wrapped
