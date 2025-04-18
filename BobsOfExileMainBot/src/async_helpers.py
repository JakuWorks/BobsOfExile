
from typing import Any, Coroutine, Callable
import asyncio
import nest_asyncio # type: ignore


def synchronize_cor[R](cor: Coroutine[Any, Any, R]) -> Callable[[], R]:
    """
    WARNINGS:
    - IF RAN WITH A INSIDE AN EVENT LOOP - WILL PATCH IT WITH nest_asyncio!!!
    - If there's no event loop, this function will use asyncio.run
    """
    def inner() -> R:
        # This could be shortened with asyncio.get_event_loop because it has exactly the same "loop getting" system
        try:
            loop = asyncio.AbstractEventLoop = asyncio.get_running_loop()
        except RuntimeError:
            # Handle the case where there's no running loop
            return asyncio.run(cor)
        # # Handle the case where there is a running loop
        nest_asyncio.apply(loop=loop) # type: ignore
        task: asyncio.Task[R] = loop.create_task(cor)
        return loop.run_until_complete(task)
    return inner


def synchronize_run[R](cor: Coroutine[Any, Any, R]) -> R:
    return synchronize_cor(cor)()