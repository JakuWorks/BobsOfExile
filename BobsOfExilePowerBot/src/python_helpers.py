from typing import Callable, Coroutine, Concatenate
from types import FrameType
import inspect


# BLATANTLY TAKEN FROM ONE OF MY OTHER PROJECTS ('BobsOfExileBot')
def get_caller(go_backs: int) -> str:
    frame: FrameType | None = inspect.currentframe()
    if frame is None:
        raise RuntimeError("Can't get frame")

    previous: FrameType | None = frame
    for i in range(go_backs):
        if previous is None:
            enacted_go_backs: int = i + 1
            raise RuntimeError(f"Cannot go back {enacted_go_backs}'th time")
        previous = previous.f_back

    if previous is None:
        raise RuntimeError(f"Cannot go back {go_backs}'th time")

    name: str = previous.f_code.co_name
    return name


def wrap_arg[**A, B, C, D, E, F](
    arg: F, func: Callable[Concatenate[F, A], Coroutine[C, D, E]]
) -> Callable[A, Coroutine[C, D, E]]:
    async def e(*args: A.args, **kwargs: A.kwargs) -> E:
        coro = func(arg, *args, **kwargs)
        ret: E = await coro
        return ret

    e.__name__ = func.__name__
    return e
