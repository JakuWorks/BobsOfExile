from typing import TypeVar, Any, Literal
from collections.abc import Set
import asyncio

# Shorthands to be used where appropriate
from asyncio import Task, Future

T = TypeVar("T")


async def wait_while_not_cancelled(
    receive_waitable: asyncio.Future[T] | asyncio.Task[T],
    cancel_waitable: asyncio.Task[Any] | asyncio.Future[Any],
    stop_receive_on_cancel: bool,
) -> tuple[Literal[True], T | None] | tuple[Literal[False], T]:
    """The receive waitable MUST NOT result in None!"""
    done: Set[Future[T] | Task[T] | Future[Any] | Task[Any]]
    pending: Set[Future[T] | Task[T] | Future[Any] | Task[Any]]
    done, pending = await asyncio.wait(
        (cancel_waitable, receive_waitable), return_when=asyncio.FIRST_COMPLETED
    )

    cancelled: bool
    if cancel_waitable in done:
        cancelled = True
    elif cancel_waitable in pending:
        cancelled = False
    else:
        assert False, "Asyncio forgot the cancel task?"

    received: T | None
    if receive_waitable in done:
        received = receive_waitable.result()
    elif receive_waitable in pending:
        received = None
        if stop_receive_on_cancel:
            receive_waitable.cancel()
    else:
        assert False, "Asyncio forgot the receive?"

    if cancelled is True:
        return cancelled, received
    assert received is not None, "Asyncio wait got nothing done?"
    return cancelled, received
