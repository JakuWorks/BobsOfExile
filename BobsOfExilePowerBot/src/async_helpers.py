from typing import Callable, Coroutine


def async_wrap[**A, R](
    fun: Callable[A, R],
) -> Callable[A, Coroutine[None, None, R]]:
    async def inner(*args: A.args, **kwargs: A.kwargs) -> R:
        return fun(*args, **kwargs)

    inner.__name__ = fun.__name__
    return inner
