from abc import ABC, abstractmethod
from typing import (
    TypeVar,
    Any,
    Literal,
    Coroutine,
    ParamSpec,
    Iterable,
    MutableMapping,
    Set,
    Callable,
)
from collections.abc import Set, Sequence, MutableSequence, Awaitable
from functools import wraps
import logging
import asyncio

T = TypeVar("T")
P = ParamSpec("P")


async def wrap_error_logging(awaitable: Awaitable[Any], on_error_msg: str) -> None:
    """
    Eats exceptions and logs them instead
    """
    try:
        await awaitable
    except Exception as e:
        logging.error(on_error_msg, exc_info=e)


async def run_some_hooks(
    hooks: Iterable[Callable[[], Awaitable[Any]]],
    msg_log_error: str | None,
    msg_log_cancelled: str | None,
) -> None:
    """
    Cancelling more than once will break the internal logic

    Catches and logs exceptions, propagates cancellations
    Waits for hooks to finish (even if cancelled once)
    """

    async def run_some_hooks_inner() -> None:
        for hook in hooks:
            logging.debug(f"Running some hook | {repr(hook)}")
            try:
                await hook()
            except Exception as e:
                if msg_log_error is not None:
                    logging.error(msg_log_error, exc_info=e)

    run_some_hooks_inner_t: asyncio.Task[None] = asyncio.create_task(
        run_some_hooks_inner()
    )
    try:
        await asyncio.shield(run_some_hooks_inner_t)
    except asyncio.CancelledError:
        logging.debug("Running some hooks got cancelled")
        if msg_log_cancelled is not None:
            logging.debug(msg_log_cancelled)
        await asyncio.shield(run_some_hooks_inner_t)
        raise
    logging.debug("Running some hooks finished")


def collect_exceptions_from_tasks(
    tasks: Iterable[asyncio.Task[Any]],
) -> tuple[Sequence[BaseException], asyncio.CancelledError | None]:
    exceptions: MutableSequence[BaseException] = []
    first_cancelled_error: asyncio.CancelledError | None = None
    for task in tasks:
        try:
            exception: BaseException | None = task.exception()
            if exception is not None:
                exceptions.append(exception)
        except asyncio.InvalidStateError:
            # "Exception is not set."
            continue
        except asyncio.CancelledError as e:
            if first_cancelled_error is None:
                first_cancelled_error = e

    return exceptions, first_cancelled_error


def collect_exceptions_from_tasks_into_group(
    tasks: Iterable[asyncio.Task[Any]], msg: str
) -> tuple[BaseExceptionGroup | None, asyncio.CancelledError | None]:
    exceptions: Sequence[BaseException]
    cancelled: asyncio.CancelledError | None
    exceptions, cancelled = collect_exceptions_from_tasks(tasks)
    exceptions_group: BaseExceptionGroup | None
    if exceptions:
        exceptions_group = BaseExceptionGroup(msg, exceptions)
    else:
        exceptions_group = None
    return exceptions_group, cancelled


async def coroutines_race(
    coroutines: Sequence[Coroutine[Any, Any, Any]],
    cancel_everything_afterwards: bool,
    exception_msg: str,
) -> tuple[Sequence[int], BaseExceptionGroup | None, asyncio.CancelledError | None]:
    """
    -> indexes of the finished coroutines, exceptions, cancelled
    Cancelling more than once will break the internal logic
    Attempts to quit as soon as any coroutine is complete
    Propagates errors
    """
    task_group: NonstructuralTaskGroup = NonstructuralTaskGroup()
    all_tasks: Sequence[asyncio.Task[Any]] = []
    for coroutine in coroutines:
        all_tasks.append(task_group.create_task(coroutine)[0])
    logging.debug("Coroutines race taking place")
    try:
        done_tasks: Set[asyncio.Task[Any]]
        pending_tasks: Set[asyncio.Task[Any]]
        done_tasks, pending_tasks = await task_group.wait_any()
    except asyncio.CancelledError:
        logging.debug("Coroutines race got cancelled")

        if cancel_everything_afterwards:
            for task in all_tasks:
                cancel_task_only_once_if_not_done(task)
            await task_group.wait_all()
        raise

    logging.debug(f"Coroutines race done tasks are | {repr(done_tasks)}")
    assert len(done_tasks) != 0
    done_indexes: MutableSequence[int] = []
    for done_task in done_tasks:
        try:
            # TODO Possibly use a mapping for this instead?
            done_indexes.append(all_tasks.index(done_task))
        except ValueError:
            pass

    exceptions: BaseExceptionGroup | None
    cancelled: asyncio.CancelledError | None
    exceptions, cancelled = collect_exceptions_from_tasks_into_group(
        done_tasks, msg=exception_msg
    )

    if cancel_everything_afterwards:
        for task in pending_tasks:
            cancel_task_only_once_if_not_done(task)
        wait_until_cancelled_t: asyncio.Task[Any] = asyncio.create_task(
            task_group.wait_all()
        )
        try:
            await asyncio.shield(wait_until_cancelled_t)
        except asyncio.CancelledError:
            # This is silly but what else can we do in this situation
            await wait_until_cancelled_t
            raise

    return done_indexes, exceptions, cancelled


def cancel_task_only_once_if_not_done(task: asyncio.Task[Any]) -> None:
    if task.cancelling() != 0:
        logging.warning(f"Attempted to cancel a task AGAIN, (repr: {repr(task)})")
        return
    if task.cancelled():
        logging.warning(
            f"Task cancelled but not cancelling is 0? It may be handling cancellations incorrectly (repr: {repr(task)})"
        )
    if task.done():
        return
    task.cancel()


def wrap_async_func_with_done_event(
    async_func: Callable[P, Coroutine[Any, Any, T]], done_event: asyncio.Event
) -> Callable[P, Coroutine[None, None, T]]:
    @wraps(async_func)
    async def wrapped_with_done_event(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            ret: T = await async_func(*args, **kwargs)
            done_event.set()
            return ret
        except BaseException:
            done_event.set()
            raise

    return wrapped_with_done_event


async def wrap_coroutine_with_done_event(
    coroutine: Coroutine[Any, Any, T], done_event: asyncio.Event
) -> T:
    try:
        ret: T = await coroutine
        done_event.set()
        return ret
    except BaseException:
        done_event.set()
        raise


class NonstructuralTaskGroupNoTasksError(Exception):
    pass


class NonstructuralTaskGroup:
    """Does not propagate exceptions and cancellations in any way on its own"""

    __slots__ = ("tasks",)

    tasks: MutableMapping[asyncio.Event, asyncio.Task[Any]]
    # Mapping[completed event, wrapped task]

    def __init__(self) -> None:
        self.tasks = {}

    def create_task(
        self, coroutine: Coroutine[Any, Any, T], name: str | None = None
    ) -> tuple[asyncio.Task[T], asyncio.Event]:
        """-> task, done_event"""
        done_event: asyncio.Event = asyncio.Event()
        wrapped: Coroutine[Any, Any, T] = wrap_coroutine_with_done_event(
            coroutine, done_event
        )
        task: asyncio.Task[T] = asyncio.create_task(wrapped, name=name)
        self.tasks[done_event] = task
        return task, done_event

    async def wait_any(self) -> tuple[Set[asyncio.Task[Any]], Set[asyncio.Task[Any]]]:
        """-> done, pending
        Does NOT cancel the real tasks when one raises an error/cancellation (only the event waits are cancelled)
        A task cancelling/raising an exception DOES count as it finishing
        """

        if len(self.tasks) == 0:
            raise NonstructuralTaskGroupNoTasksError
        event_tasks: MutableMapping[asyncio.Task[Literal[True]], asyncio.Event] = dict()
        for event in self.tasks.keys():
            wait_task: asyncio.Task[Literal[True]] = asyncio.create_task(event.wait())
            event_tasks[wait_task] = event

        cancelled: asyncio.CancelledError | None = None
        done_events: Set[asyncio.Task[Any]] | None = None
        pending_events: Set[asyncio.Task[Any]] | None = None
        try:
            done_events, pending_events = await asyncio.wait(
                event_tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError as e:
            # We got cancelled (or our caller) (it's almost impossible that it was the event task)
            cancelled = e

        for event_task in event_tasks.keys():
            cancel_task_only_once_if_not_done(event_task)

        if cancelled is not None:
            raise cancelled
        assert done_events is not None
        assert pending_events is not None

        done_tasks: Set[asyncio.Task[Any]] = {
            self.tasks[event_tasks[done_event]] for done_event in done_events
        }
        pending_tasks: Set[asyncio.Task[Any]] = {
            self.tasks[event_tasks[pending_event]] for pending_event in pending_events
        }
        return done_tasks, pending_tasks

    async def wait_all(self) -> tuple[Set[asyncio.Task[Any]], Set[asyncio.Task[Any]]]:
        """-> done, pending
        Does NOT cancel the real tasks when one raises an error/cancellation (only the event waits are cancelled)
        A task cancelling/raising an exception DOES count as it finishing
        """
        if len(self.tasks) == 0:
            raise NonstructuralTaskGroupNoTasksError
        event_waits_tasks: MutableMapping[
            asyncio.Task[Literal[True]], asyncio.Event
        ] = dict()
        for event in self.tasks.keys():
            wait_task: asyncio.Task[Literal[True]] = asyncio.create_task(event.wait())
            event_waits_tasks[wait_task] = event

        cancelled: asyncio.CancelledError | None = None
        done_events: Set[asyncio.Task[Any]] | None = None
        pending_events: Set[asyncio.Task[Any]] | None = None
        try:
            done_events, pending_events = await asyncio.wait(
                event_waits_tasks.keys(), return_when=asyncio.ALL_COMPLETED
            )
        except asyncio.CancelledError as e:
            # We got cancelled (or our caller) (it's almost impossible that it was the event task)
            cancelled = e

        for event_task in event_waits_tasks:
            cancel_task_only_once_if_not_done(event_task)

        if cancelled is not None:
            raise cancelled
        assert done_events is not None
        assert pending_events is not None

        done_tasks: Set[asyncio.Task[Any]] = {
            self.tasks[event_waits_tasks[done_event]] for done_event in done_events
        }
        pending_tasks: Set[asyncio.Task[Any]] = {
            self.tasks[event_waits_tasks[pending_event]]
            for pending_event in pending_events
        }
        return done_tasks, pending_tasks

    def tasks_count(self) -> int:
        return len(self.tasks)


class IPhaseNumber(ABC):
    @abstractmethod
    def get_max(self) -> int: ...
    @abstractmethod
    def get(self) -> int: ...
    @abstractmethod
    async def wait(self, num: int) -> None: ...


class IMutablePhaseNumber(IPhaseNumber):
    @abstractmethod
    def set(self, value: int) -> None: ...
    @abstractmethod
    def increment(self) -> None: ...


class PhaseNumber(IMutablePhaseNumber):
    __slots__ = ("_event", "_current", "_max", "_log_setting_format")

    _events: Sequence[asyncio.Event]
    _current: int
    _max: int
    _log_setting_format: str | None

    def __init__(self, max_phase: int, log_setting_format: str | None) -> None:
        self._current = 0
        self._events = tuple(asyncio.Event() for _ in range(max_phase + 1))
        self._max = max_phase
        self._log_setting_format = log_setting_format

    def get_max(self) -> int:
        return self._max

    def get(self) -> int:
        return self._current

    async def wait(self, num: int) -> None:
        if num > self._max:
            raise ValueError(f"Too high ({num=} {self._current=})")
        await self._events[num].wait()

    def set(self, value: int) -> None:
        if value < 0:
            raise ValueError(f"Setting phase too low ({value=})")
        if value > self._max:
            raise ValueError(f"Setting phase too high ({value=} {self._max=})")
        if value - self._current != 1:
            raise ValueError(f"Setting phase out of order {value=} {self._current=}") # fmt: skip
        if self._log_setting_format is not None:
            logging.debug(self._log_setting_format.format(str(value)))
        self._current = value
        self._events[value].set()

    def increment(self) -> None:
        self.set(self._current + 1)


class IBooleanEvent(ABC):
    @abstractmethod
    async def wait(self) -> None: ...
    @abstractmethod
    def get(self) -> bool: ...


class IMutableBooleanEvent(IBooleanEvent):
    @abstractmethod
    def set(self) -> None: ...


class IUnsettableBooleanEvent(ABC):
    @abstractmethod
    async def wait(self) -> None: ...
    @abstractmethod
    async def wait_false(self) -> None: ...
    @abstractmethod
    def get(self) -> bool: ...


class IMutableUnsettableBooleanEvent(IUnsettableBooleanEvent):
    @abstractmethod
    def set(self) -> None: ...
    @abstractmethod
    def unset(self) -> None: ...


class BooleanEvent(IMutableBooleanEvent):
    __slots__ = ("set_msg", "set_again_warning", "_event")

    set_msg: str | None
    set_again_warning: str | None
    _event: asyncio.Event

    def __init__(
        self,
        set_msg: str | None,
        set_again_warning: str | None,
    ) -> None:
        self.set_msg = set_msg
        self.set_again_warning = set_again_warning
        self._event = asyncio.Event()

    def set(self) -> None:
        if self.set_again_warning is not None and self._event.is_set():
            logging.warning(self.set_again_warning)
        elif self.set_msg is not None:
            logging.info(self.set_msg)
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def get(self) -> bool:
        return self._event.is_set()


class UnsettableBooleanEvent(IMutableUnsettableBooleanEvent):
    __slots__ = (
        "unset_msg",
        "unset_again_warning",
        "_event_negative",
        "set_msg",
        "set_again_warning",
        "_event",
    )

    set_msg: str | None
    set_again_warning: str | None
    _event: asyncio.Event

    unset_msg: str | None
    unset_again_warning: str | None
    _event_negative: asyncio.Event

    def __init__(
        self,
        set_msg: str | None,
        unset_msg: str | None,
        set_again_warning: str | None,
        unset_again_warning: str | None,
    ) -> None:
        self.set_msg = set_msg
        self.set_again_warning = set_again_warning
        self._event = asyncio.Event()

        self.unset_msg = unset_msg
        self.unset_again_warning = unset_again_warning
        self._event_negative = asyncio.Event()
        self._event_negative.set()

    def set(self) -> None:
        if self.set_again_warning is not None and self._event.is_set():
            logging.warning(self.set_again_warning)
        elif self.set_msg is not None:
            logging.info(self.set_msg)
        self._event.set()
        self._event_negative.clear()

    def unset(self) -> None:
        if self.unset_again_warning is not None and not self._event.is_set():
            logging.warning(self.unset_again_warning)
        elif self.unset_msg is not None:
            logging.info(self.unset_msg)
        self._event.clear()
        self._event_negative.set()

    async def wait(self) -> None:
        await self._event.wait()

    async def wait_false(self) -> None:
        await self._event_negative.wait()

    def get(self) -> bool:
        assert self._event.is_set() is not self._event_negative.is_set()
        return self._event.is_set()
