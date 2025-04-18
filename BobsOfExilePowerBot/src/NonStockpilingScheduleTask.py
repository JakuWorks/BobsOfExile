from typing import Callable, Coroutine, Any
import schedule
import time
import asyncio
from common import AnyCoroutine
from OTHER_SETTINGS import LOGS_SEPARATOR as s
from logs import ldbg, lwarn
from async_helpers import async_wrap


_async_run_pending: Callable[[], Coroutine[None, None, None]] = async_wrap(
    schedule.run_pending
)


class NonStockpilingScheduleTask:
    SAFETY_AUTO_RUN_DELAY_ADD: float = 0.5
    SAFETY_MIN_ALLOWED_TIMESTAMP_SUBTRACT: float = 0.5
    last_run: float  # timestamp

    def __init__(
        self,
        job: Callable[[], AnyCoroutine],
        loop: asyncio.AbstractEventLoop,
        every_secs: int,
    ) -> None:
        logs_infix: str = f"Job: {job.__name__}{s}Every Secs: {every_secs}{s}"
        ldbg(f"{logs_infix}Creating a new NonStockpilingScheduleTask")
        bonus: float = self.SAFETY_AUTO_RUN_DELAY_ADD
        safe_every_secs = every_secs + bonus
        self.last_run = 0.0

        with_auto_pending: Callable[[], AnyCoroutine] = self.wrap_auto_run_pending(
            job, safe_every_secs
        )
        with_non_stockpiling: Callable[[], AnyCoroutine] = self.wrap_non_stockpiling(
            with_auto_pending, every_secs
        )
        as_sync: Callable[[], Any] = self.wrap_job_sync(with_non_stockpiling, loop)
        schedule.every(every_secs).seconds.do(as_sync)  # type: ignore
        loop.create_task(self.delayed_run(_async_run_pending(), safe_every_secs))

    def wrap_non_stockpiling(
        self, job: Callable[[], AnyCoroutine], every_secs: float
    ) -> Callable[[], AnyCoroutine]:
        async def inner() -> None:
            DECIMALS: int = 2
            now: float = time.time()
            allowed_subtract: float = self.SAFETY_MIN_ALLOWED_TIMESTAMP_SUBTRACT
            allowed: float = self.last_run + every_secs - allowed_subtract
            logs_infix: str = (
                f"NonStockpilingScheduleTask{s}Now: {now:.{DECIMALS}f}{s}"
                f"Allowed since: {allowed:.{DECIMALS}f}{s}"
            )
            ldbg(f"{logs_infix}Running non-stockpiling scheduled job")
            if now < allowed:
                lwarn(
                    f"{logs_infix}Tried running scheduled task but it wasn't ready yet!"
                    f"This may be an error! Removing this task from the auto run pending schedule!"

                )
                return
            self.last_run = now
            await job()
            return

        inner.__name__ = job.__name__
        return inner

    def wrap_auto_run_pending(
        self, job: Callable[[], AnyCoroutine], delay_secs: float
    ) -> Callable[[], AnyCoroutine]:
        async def inner() -> None:
            await job()
            await self.delayed_run(_async_run_pending(), delay_secs)

        inner.__name__ = job.__name__
        return inner

    def wrap_job_sync(
        self, job: Callable[[], AnyCoroutine], loop: asyncio.AbstractEventLoop
    ) -> Callable[[], Any]:
        def inner() -> None:
            loop.create_task(job())

        inner.__name__ = job.__name__
        return inner

    async def delayed_run(self, coro: AnyCoroutine, delay_secs: float) -> None:
        await asyncio.sleep(delay_secs)
        await coro
