from typing import Any, Coroutine, Callable, Iterable, Set, TypedDict, Required
from typing_extensions import ReadOnly
from collections import deque
from collections.abc import Set, MutableMapping, Sequence, MutableSequence
import logging
import pathlib
import asyncio.subprocess
import asyncio

import mcstatus
import mcstatus.responses

from .subprocess_convenience import (
    terminate_and_kill_process_group_and_wait_for_process,
)
from .hardcoded import (
    MINECRAFT_STDOUT_PER_READ_MAX_BYTES,
    MINECRAFT_STATUS_CHECK_TIMEOUT_SECONDS,
    MINECRAFT_STATUS_CHECK_PROTOCOL_MAGIC_VERSION_VALUE_LEGACY,
    MINECRAFT_STATUS_CHECK_TRIES,
    MINECRAFT_EMPTINESS_MONITOR_STATUS_TIMEOUT_S,
    MINECRAFT_EMPTINESS_MONITOR_NOTIFY_EMPTY_TIMEOUT_S,
    MINECRAFT_EMPTINESS_MONITOR_NOTIFY_NOT_EMPTY_TIMEOUT_S,
)
from .async_convenience import (
    cancel_task_only_once_if_not_done,
    collect_exceptions_from_tasks_into_group,
    NonstructuralTaskGroup,
    PhaseNumber,
    IMutablePhaseNumber,
    IPhaseNumber,
    BooleanEvent,
    IMutableBooleanEvent,
    IBooleanEvent,
    IMutableUnsettableBooleanEvent,
    UnsettableBooleanEvent,
    IUnsettableBooleanEvent,
    coroutines_race,
    run_some_hooks,
    wrap_error_logging,
)
from .minecraft_convenience import MinecraftEntryConfigFromEnv
from .minecraft_ram import IMinecraftRamCounter, IReadableMinecraftRamCounter

# TODO Add public named constants for startup phases and use them everywhere instead


class MinecraftError(Exception):
    pass


class OneTimeMinecraftInstanceError(MinecraftError):
    pass


class OneTimeMinecraftInstanceInvalidStateError(OneTimeMinecraftInstanceError):
    pass


class OneTimeMinecraftInstanceExecutableMissingError(OneTimeMinecraftInstanceError):
    pass


class OneTimeMinecraftInstanceMissingStdinError(OneTimeMinecraftInstanceError):
    pass


class OneTimeMinecraftInstanceMissingStdoutError(OneTimeMinecraftInstanceError):
    pass


class OneTimeMinecraftInstance:
    __slots__ = (
        "start_executable",
        "_startup_phase",
        "_stopping_event",
        "_empty_streak",
        "_start_task",
        "_on_empty_hooks",
        "_on_empty_prolonged_hooks",
        "_stdout_buffer",
        "_empty_prolonged_minimum_streak",
        "_enable_empty_monitoring",
        "_status_check_host",
        "_status_check_port",
        "_status_check_protocol_version",
        "_stop_kill_bonus_delay",
        "_stop_on_empty_prolonged",
        "_stop_terminate_attempts",
        "_stop_terminate_interval",
        "_process",
        "_stdin_pipe",
        "_stdin_queue",
        "_stdout_pipe",
    )

    # Must be a valid os executable (runnable with just ./scriptpath) (e.g. you need a shebang for linux .sh scripts)
    # Also the executable must be able to pass through signals (so use 'exec' for .sh scripts)

    # Assigned on startup zero (init)
    start_executable: pathlib.Path

    _startup_phase: IMutablePhaseNumber
    _stopping_event: IMutableBooleanEvent

    # Assigned between zero and one
    _empty_streak: int | None
    _start_task: asyncio.Task[Any] | None

    # fmt: off
    _on_empty_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None
    _on_empty_prolonged_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None
    _stdout_buffer: deque[int] | None
    # fmt: on

    _empty_prolonged_minimum_streak: int | None
    _enable_empty_monitoring: bool | None
    _status_check_host: str | None
    _status_check_port: int | None
    _status_check_protocol_version: int | None
    _stop_kill_bonus_delay: float | None
    _stop_on_empty_prolonged: bool | None
    _stop_terminate_attempts: int | None
    _stop_terminate_interval: float | None

    # Assigned between one and two
    _process: asyncio.subprocess.Process | None
    _stdin_pipe: asyncio.StreamWriter | None
    _stdin_queue: asyncio.Queue[bytes] | None
    _stdout_pipe: asyncio.StreamReader | None

    # Nothing is assigned between two and three

    def __init__(
        self,
        start_executable: pathlib.Path,
    ) -> None:
        logging.info(f"Making a new server instance | start executable: {str(start_executable)}") # fmt: skip

        # -
        start_executable = start_executable.expanduser().resolve(strict=True).absolute()
        if not start_executable.exists():
            raise OneTimeMinecraftInstanceExecutableMissingError(
                f"Start executable doesn't exist ({start_executable=})"
            )
        self.start_executable = start_executable
        # -

        log_setting_format: str = (
            "Setting one-time minecraft instance startup phase as {}"
        )
        self._startup_phase = PhaseNumber(
            max_phase=3, log_setting_format=log_setting_format
        )

        self._stopping_event = BooleanEvent(
            set_msg="Setting one-time minecraft instance as stopping",
            set_again_warning="Setting one-time minecraft instance as stopping AGAIN",
        )

        self._empty_streak = None
        self._start_task = None

        self._on_empty_hooks = None
        self._on_empty_prolonged_hooks = None
        self._stdout_buffer = None

        self._empty_prolonged_minimum_streak = None
        self._enable_empty_monitoring = None
        self._status_check_host = None
        self._status_check_port = None
        self._status_check_protocol_version = None
        self._stop_kill_bonus_delay = None
        self._stop_on_empty_prolonged = None
        self._stop_terminate_attempts = None
        self._stop_terminate_interval = None

        self._stdout_pipe = None
        self._stdin_pipe = None
        self._stdin_queue = None
        self._process = None

    @classmethod
    async def create_process(
        cls, start_executable: pathlib.Path, cwd: pathlib.Path
    ) -> tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader]:
        """
        -> process, stdin, stdout
        May assist in startup
        """
        process: asyncio.subprocess.Process = (
            await asyncio.subprocess.create_subprocess_exec(
                program=start_executable,
                cwd=cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                text=False,
                bufsize=0,
                start_new_session=True,
            )
        )
        logging.info(f"Created a process for the one-time minecraft instance | {process.pid}") # fmt: skip
        # TODO: Is it safe to just kill it here?
        # I'll keep it for now because I think that it's safe to do as long as it's extremely early in the starting process
        # Hopefully...
        try:
            if process.stdin is None:
                process.kill()
                await process.wait()
                raise OneTimeMinecraftInstanceMissingStdinError
            if process.stdout is None:
                process.kill()
                await process.wait()
                raise OneTimeMinecraftInstanceMissingStdoutError
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            raise
        return process, process.stdin, process.stdout

    async def start(
        # fmt: off
        self,
        empty_prolonged_minimum_streak: int,
        enable_empty_monitoring: bool,
        status_check_host: str,
        status_check_port: int,
        status_check_protocol_version: int,
        stop_kill_bonus_delay: float,
        stop_on_empty_prolonged: bool,
        stop_terminate_attempts: int,
        stop_terminate_interval: float,

        stdout_buffer: deque[int],
        on_empty_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_empty_prolonged_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_stopping_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        # fmt: on
    ) -> None:
        """
        Must be ran in a cancellable task
        Must be ran only once
        Cancelling more than once will break the internal logic
        Cancelling while stopping will break the internal logic
        The task running this method must be cancelled in order to stop the instance
        """
        # Errors coming from created tasks should not break the internal logic
        # Uncaught errors inside this method will break the internal logic (e.g. hooks won't be called, events won't be set)
        self.ensure_startup_eq_zero()
        self.ensure_not_stopping()

        current_task: asyncio.Task[Any] | None = asyncio.current_task()
        assert current_task is not None

        self._empty_prolonged_minimum_streak = empty_prolonged_minimum_streak
        self._enable_empty_monitoring = enable_empty_monitoring
        self._status_check_host = status_check_host
        self._status_check_port = status_check_port
        self._status_check_protocol_version = status_check_protocol_version
        self._stop_kill_bonus_delay = stop_kill_bonus_delay
        self._stop_on_empty_prolonged = stop_on_empty_prolonged
        self._stop_terminate_attempts = stop_terminate_attempts
        self._stop_terminate_interval = stop_terminate_interval

        self._on_empty_hooks = on_empty_hooks
        self._on_empty_prolonged_hooks = on_empty_prolonged_hooks
        self._stdout_buffer = stdout_buffer

        self._empty_streak = 0
        self._start_task = current_task
        self._startup_phase.set(1)

        async def run_on_stopping_hooks():
            if on_stopping_hooks is not None:
                await run_some_hooks(
                    hooks=on_stopping_hooks,
                    msg_log_error="One-time minecraft instance got an error while running a stopping hook",
                    msg_log_cancelled="Contract violation in one-time minecraft instance",  # Silly but why not log it here if it's so easy to do anyway
                )

        cwd: pathlib.Path = self.start_executable.parent
        try:
            process: asyncio.subprocess.Process
            stdin_pipe: asyncio.StreamWriter
            stdout_pipe: asyncio.StreamReader
            process, stdin_pipe, stdout_pipe = await self.create_process(
                start_executable=self.start_executable, cwd=cwd
            )
        except asyncio.CancelledError:
            # Yes we can get cancelled; no we don't have to cleanup anything yet
            logging.info("One-time minecraft instance got cancelled while not fully started") # fmt: skip
            self._stopping_event.set()
            raise
        except Exception:
            # TODO Specify exceptions
            logging.error("One-time minecraft instance failed to create a process") # fmt: skip
            self._stopping_event.set()
            await run_on_stopping_hooks()
            raise

        self._process = process
        self._stdin_pipe = stdin_pipe
        self._stdin_queue = asyncio.Queue()
        self._stdout_pipe = stdout_pipe
        self._startup_phase.set(2)

        # Cannot use asyncio's standard task groups due to the more complex cancellation order

        tasks_group: NonstructuralTaskGroup = NonstructuralTaskGroup()

        stdout_receiver: asyncio.Task[None]
        stdout_receiver, _ = tasks_group.create_task(self._start_stdout_receiver())
        stdin_writer: asyncio.Task[None]
        stdin_writer, _ = tasks_group.create_task(self._start_stdin_writer())
        process_exit_waiter: asyncio.Task[int]
        process_exit_waiter, _ = tasks_group.create_task(process.wait())

        # Operation

        self._startup_phase.set(3)

        self_cancelled: asyncio.CancelledError | Exception | None = None
        try:
            _, _ = await tasks_group.wait_any()
        except asyncio.CancelledError as e:
            self_cancelled = e
            logging.info("One-time minecraft instance got cancelled")

        # Cleanup

        # Trusts that this task won't be cancelled while stopping
        # (it would be silly to try to catch these especially when a cancellation can happen multiple times)

        self._stopping_event.set()

        await run_on_stopping_hooks()

        cancel_task_only_once_if_not_done(stdin_writer)
        cancel_task_only_once_if_not_done(process_exit_waiter)
        await self._stop_process()
        await self._get_process().wait()
        cancel_task_only_once_if_not_done(stdout_receiver)

        cleanup_done: Set[asyncio.Task[Any]]
        cleanup_pending: Set[asyncio.Task[Any]]
        cleanup_done, cleanup_pending = await tasks_group.wait_all()
        assert len(cleanup_pending) == 0, "Not all tasks were finished in one-time minecraft instance while stopping!" # fmt: skip
        assert len(cleanup_done) != 0, "No tasks were done in one-time minecraft instance while stopping!" # fmt: skip
        assert len(cleanup_done) == tasks_group.tasks_count(), "Some tasks were lost in one-time minecraft instance while stopping!" # fmt: skip

        tasks_exceptions: BaseExceptionGroup | None
        tasks_cancelled: asyncio.CancelledError | None
        tasks_exceptions, tasks_cancelled = collect_exceptions_from_tasks_into_group(
            cleanup_done, msg="Exceptions in one-time minecraft instance"
        )

        if tasks_exceptions:
            logging.error(f"One-time minecraft instance finished with exceptions! {repr(tasks_exceptions)}") # fmt: skip
            raise tasks_exceptions
        if self_cancelled:
            logging.info(f"One-time minecraft instance got cancelled, cleaned up and finished") # fmt: skip
            raise self_cancelled
        if tasks_cancelled:
            logging.info(f"One-time minecraft instance's task got cancelled (so it cleaned up and finished)") # fmt: skip
            raise tasks_cancelled
        logging.info("One-time minecraft instance finished")

    async def _start_stdin_writer(self) -> None:
        """
        At least two and not stopping
        Cancelling more than once will break the internal logic
        """
        self.ensure_startup_ge_two()
        self.ensure_not_stopping()

        cancelled: asyncio.CancelledError | None = None

        process: asyncio.subprocess.Process = self._get_process()  # Only used for a failsafe # fmt: skip
        stdin_pipe: asyncio.StreamWriter = self._get_stdin_pipe()
        stdin_queue: asyncio.Queue[bytes] = self._get_stdin_queue()

        logging.info("One-time minecraft instance stdin writer started")
        while True:
            try:
                data_to_send: bytes = await stdin_queue.get()
            except asyncio.CancelledError as e:
                cancelled = e
                logging.info("One-time minecraft instance stdin writer got cancelled while awaiting input") # fmt: skip
                break

            if process.returncode is not None:
                logging.info(f"One-time minecraft instance stdin writer got return code {process.returncode}") # fmt: skip
                break

            stdin_pipe.write(data_to_send)

        logging.info("One-time minecraft instance stdin writer finished")
        if cancelled is not None:
            raise cancelled

    async def _start_stdout_receiver(
        self,
    ) -> None:
        """
        At least two and not stopping
        Cancelling more than once will break the internal logic
        """
        self.ensure_startup_ge_two()
        self.ensure_not_stopping()

        cancelled: asyncio.CancelledError | None = None

        stdout_buffer: deque[int] = self.get_stdout_buffer()
        stdout_pipe: asyncio.StreamReader = self._get_stdout_pipe()
        process: asyncio.subprocess.Process = self._get_process()  # Only used for a failsafe # fmt: skip

        logging.info("One-time minecraft instance stdout receiver started")
        while True:
            if process.returncode is not None:
                logging.info(f"One-time minecraft instance stdout receiver got return code {process.returncode}") # fmt: skip
                break

            try:
                out: bytes = await stdout_pipe.read(
                    n=MINECRAFT_STDOUT_PER_READ_MAX_BYTES
                )
            except asyncio.CancelledError as e:
                cancelled = e
                logging.info("One-time minecraft instance stdout receiver cancelled while awaiting input") # fmt: skip
                break

            if out == b"":
                # EOF read
                logging.info("One-time minecraft instance stdout receiver got empty (EOF) read") # fmt: skip
                break

            stdout_buffer.extend(out)

        logging.info("One-time minecraft instance stdout receiver finished")
        if cancelled is not None:
            raise cancelled

    def stop(self) -> None:
        """
        At least one and not stopping
        Works by cancelling the task
        """
        self.ensure_startup_ge_one()
        self.ensure_not_stopping()
        start_task: asyncio.Task[Any] = self.get_start_task()
        cancel_task_only_once_if_not_done(start_task)

    async def _stop_process(
        self,
    ) -> None:
        """
        At least 2
        """
        self.ensure_startup_ge_two()
        process: asyncio.subprocess.Process = self._get_process()
        stop_kill_bonus_delay: float = self._get_stop_kill_bonus_delay()
        stop_terminate_attempts: int = self._get_stop_terminate_attempts()
        stop_terminate_interval: float = self._get_stop_terminate_interval()

        await terminate_and_kill_process_group_and_wait_for_process(
            process=process,
            kill_bonus_delay=stop_kill_bonus_delay,
            terminate_attempts=stop_terminate_attempts,
            terminate_interval=stop_terminate_interval,
        )

    async def send_command(self, text: str) -> None:
        """
        At least two and not stopping
        """
        self.ensure_startup_ge_two()
        self.ensure_not_stopping()
        stdin_queue: asyncio.Queue[bytes] = self._get_stdin_queue()

        text_with_enter: str = text + "\n"
        to_write: bytes = text_with_enter.encode("utf-8", errors="strict")
        await stdin_queue.put(to_write)

    async def get_status(
        self,
    ) -> mcstatus.responses.BaseStatusResponse:
        """
        At least 2 and not stopping
        """
        self.ensure_startup_ge_two()
        self.ensure_not_stopping()
        status_check_protocol_version: int = self._get_status_check_protocol_version()
        status: mcstatus.responses.BaseStatusResponse
        if (
            status_check_protocol_version
            == MINECRAFT_STATUS_CHECK_PROTOCOL_MAGIC_VERSION_VALUE_LEGACY
        ):
            logging.debug("One-time minecraft instance getting status getting new legacy status checker") # fmt: skip
            legacy_status_checker: mcstatus.LegacyServer = (
                self._get_new_legacy_status_checker()
            )
            logging.debug("One-time minecraft instance getting status") # fmt: skip
            status = await legacy_status_checker.async_status(
                tries=MINECRAFT_STATUS_CHECK_TRIES
            )
            return status
        else:
            logging.debug("One-time minecraft instance getting status getting new status checker") # fmt: skip
            status_checker: mcstatus.JavaServer = self._get_new_status_checker()
            logging.debug("One-time minecraft instance getting status") # fmt: skip
            status = await status_checker.async_status(
                tries=MINECRAFT_STATUS_CHECK_TRIES,
                version=status_check_protocol_version,
            )
            return status

    async def notify_not_empty(self) -> None:
        """
        At least 2 and not stopping
        May be called whenever a user of this class deems this instance not empty
        """
        self.ensure_startup_ge_two()
        self.ensure_not_stopping()
        enable_empty_monitoring: bool = self.get_enable_empty_monitoring()

        if not enable_empty_monitoring:
            return

        self._empty_streak = 0

    async def notify_empty(self) -> None:
        """
        At least 2 and not stopping
        May be called whenever a user of this class deems this instance empty
        """
        self.ensure_startup_ge_two()
        self.ensure_not_stopping()
        # I'm not sure if this is the correct way to program this functionality
        # The "notifying" is certainly a way to do it but is it the correct way?
        streak: int = self.get_empty_streak()
        empty_prolonged_minimum_streak: int = self._get_empty_prolonged_minimum_streak()
        stop_on_empty_prolonged: bool = self._get_stop_on_empty_prolonged()
        enable_empty_monitoring: bool = self.get_enable_empty_monitoring()

        if not enable_empty_monitoring:
            return

        if streak < empty_prolonged_minimum_streak:
            self._empty_streak = streak + 1
            await self._run_on_empty_hooks()
        else:
            self._empty_streak = 0
            await self._run_on_empty_prolonged_hooks()
            if stop_on_empty_prolonged and not self._stopping_event.get():
                self.stop()
            return

    async def _run_on_empty_hooks(
        self,
    ) -> Callable[[], Coroutine[Any, Any, Any]] | None:
        """
        At least 2 and not stopping
        """
        self.ensure_startup_ge_two()
        self.ensure_not_stopping()

        if self._on_empty_hooks is not None:
            await run_some_hooks(
                hooks=self._on_empty_hooks,
                msg_log_error="Got an error while running an emptiness hook of the one-time minecraft instance",
                msg_log_cancelled="Got cancelled while running emptiness hooks of the one-time minecraft instance",
            )

    async def _run_on_empty_prolonged_hooks(self) -> None:
        """At least 2 and not stopping"""
        self.ensure_startup_ge_two()
        self.ensure_not_stopping()

        if self._on_empty_prolonged_hooks is not None:
            await run_some_hooks(
                hooks=self._on_empty_prolonged_hooks,
                msg_log_error="Got an error while running a prolonged emptiness hook of the one-time minecraft instance",
                msg_log_cancelled="Got cancelled while running prolonged emptiness hooks of the one-time minecraft instance",
            )

    # ---

    # Making getters for some private attributes too because I don't trust
    # myself that this code works yet, later they may be replaced with the normal
    # dot lookups because these private getters aren't worth the effort (and there are missing setters for them)

    def get_empty_streak(self) -> int:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._empty_streak is not None
        return self._empty_streak

    def get_start_task(self) -> asyncio.Task[Any]:
        """At least 1"""
        # The user already has the task so it would be silly to make it private
        self.ensure_startup_ge_one()
        assert self._start_task is not None
        return self._start_task

    def get_stdout_buffer(self) -> deque[int]:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._stdout_buffer is not None
        return self._stdout_buffer

    def _get_empty_prolonged_minimum_streak(self) -> int:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._empty_prolonged_minimum_streak is not None
        return self._empty_prolonged_minimum_streak

    def get_enable_empty_monitoring(self) -> bool:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._enable_empty_monitoring is not None
        return self._enable_empty_monitoring

    def _get_status_check_host(self) -> str:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._status_check_host is not None
        return self._status_check_host

    def _get_status_check_port(self) -> int:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._status_check_port is not None
        return self._status_check_port

    def _get_status_check_protocol_version(self) -> int:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._status_check_protocol_version is not None
        return self._status_check_protocol_version

    def _get_stop_kill_bonus_delay(self) -> float:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._stop_kill_bonus_delay is not None
        return self._stop_kill_bonus_delay

    def _get_stop_on_empty_prolonged(self) -> bool:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._stop_on_empty_prolonged is not None
        return self._stop_on_empty_prolonged

    def _get_stop_terminate_attempts(self) -> int:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._stop_terminate_attempts is not None
        return self._stop_terminate_attempts

    def _get_stop_terminate_interval(self) -> float:
        """At least 1"""
        self.ensure_startup_ge_one()
        assert self._stop_terminate_interval is not None
        return self._stop_terminate_interval

    def _get_process(self) -> asyncio.subprocess.Process:
        """At least 2"""
        self.ensure_startup_ge_two()
        assert self._process is not None
        return self._process

    def _get_new_status_checker(self) -> mcstatus.JavaServer:
        """At least 1"""
        self.ensure_startup_ge_one()
        status_check_host: str = self._get_status_check_host()
        status_check_port: int = self._get_status_check_port()
        status_check_protocol_version: int = self._get_status_check_protocol_version()
        assert status_check_protocol_version != MINECRAFT_STATUS_CHECK_PROTOCOL_MAGIC_VERSION_VALUE_LEGACY, "must be legacy" # fmt: skip

        try:
            status_checker = mcstatus.JavaServer(
                host=status_check_host,
                port=status_check_port,
                timeout=MINECRAFT_STATUS_CHECK_TIMEOUT_SECONDS,
                query_port=status_check_port,
            )
        except Exception:
            # TODO Specify exceptions
            logging.error("One-time minecraft instance failed to create a status checker") # fmt: skip
            self._stopping_event.set()
            raise

        return status_checker

    def _get_new_legacy_status_checker(self) -> mcstatus.LegacyServer:
        """At least 1"""
        self.ensure_startup_ge_one()
        status_check_host: str = self._get_status_check_host()
        status_check_port: int = self._get_status_check_port()
        status_check_protocol_version: int = self._get_status_check_protocol_version()
        assert status_check_protocol_version == MINECRAFT_STATUS_CHECK_PROTOCOL_MAGIC_VERSION_VALUE_LEGACY, "must not be legacy" # fmt: skip

        try:
            status_checker = mcstatus.LegacyServer(
                host=status_check_host,
                port=status_check_port,
                timeout=MINECRAFT_STATUS_CHECK_TIMEOUT_SECONDS,
            )
        except Exception:
            # TODO Specify exceptions
            logging.error("One-time minecraft instance failed to create a status checker") # fmt: skip
            self._stopping_event.set()
            raise

        return status_checker

    def _get_stdout_pipe(self) -> asyncio.StreamReader:
        """At least 2"""
        self.ensure_startup_ge_two()
        assert self._stdout_pipe is not None
        return self._stdout_pipe

    def _get_stdin_queue(self) -> asyncio.Queue[bytes]:
        """At least 2"""
        self.ensure_startup_ge_two()
        assert self._stdin_queue is not None
        return self._stdin_queue

    def _get_stdin_pipe(self) -> asyncio.StreamWriter:
        """At least 2"""
        self.ensure_startup_ge_two()
        assert self._stdin_pipe is not None
        return self._stdin_pipe

    # -

    def get_stopping_event(self) -> IBooleanEvent:
        return self._stopping_event

    def ensure_not_stopping(self) -> None:
        if self._stopping_event.get():
            raise OneTimeMinecraftInstanceInvalidStateError("Must not be stopping")

    def get_startup_phase(self) -> IPhaseNumber:
        return self._startup_phase

    async def wait_startup_phase(self, phase: int) -> None:
        await self._startup_phase.wait(phase)

    def ensure_startup_eq_zero(self) -> None:
        if self.get_startup_phase().get() != 0:
            raise OneTimeMinecraftInstanceInvalidStateError("Startup phase must == 0")

    def ensure_startup_ge_one(self) -> None:
        if self.get_startup_phase().get() < 1:
            raise OneTimeMinecraftInstanceInvalidStateError("Startup phase must >= 1")

    def ensure_startup_ge_two(self) -> None:
        if self.get_startup_phase().get() < 2:
            raise OneTimeMinecraftInstanceInvalidStateError("Startup phase must >= 2")

    def ensure_startup_ge_three(self) -> None:
        if self.get_startup_phase().get() < 3:
            raise OneTimeMinecraftInstanceInvalidStateError("Startup phase must >= 3")


class MinecraftInstanceEntryError(MinecraftError):
    pass


class MinecraftInstanceEntryInvalidStateError(MinecraftInstanceEntryError):
    pass


class MinecraftInstanceEntryAlreadyRunningError(MinecraftInstanceEntryInvalidStateError): # fmt: skip
    pass


class MinecraftInstanceEntryNotRunningError(MinecraftInstanceEntryInvalidStateError):
    pass


class MinecraftInstanceEntry:
    __slots__ = (
        "name",
        "start_executable",
        "estimated_max_ram_usage_bytes",
        "_stdout_buffer",
        "_running_event",
        "_running_instance",
        "_running_task",
    )

    # Assigned on init
    name: str
    start_executable: pathlib.Path
    estimated_max_ram_usage_bytes: int
    _stdout_buffer: deque[int]
    _running_event: IMutableUnsettableBooleanEvent

    # Assigned while running
    _running_instance: OneTimeMinecraftInstance | None
    _running_task: asyncio.Task[None] | None

    def __init__(
        self,
        name: str,
        start_executable: pathlib.Path,
        estimated_max_ram_usage_bytes: int,
        stdout_buffer_max_bytes: int,
    ) -> None:
        self.name = name
        self.estimated_max_ram_usage_bytes = estimated_max_ram_usage_bytes
        self.start_executable = start_executable
        self._stdout_buffer = deque(maxlen=stdout_buffer_max_bytes)
        self._running_event = UnsettableBooleanEvent(
            set_msg="Setting one-time minecraft instance as running",
            unset_msg="Unsetting one-time minecraft instance running",
            set_again_warning="Setting one-time minecraft instance as running AGAIN",
            unset_again_warning="Unsetting one-time minecraft instance running AGAIN",
        )

        self._running_instance = None
        self._running_task = None

    def start_as_task(
        # fmt: off
        self,
        empty_prolonged_minimum_streak: int,
        enable_empty_monitoring: bool,
        status_check_host: str,
        status_check_port: int,
        status_check_protocol_version: int,
        stop_kill_bonus_delay: float,
        stop_on_empty_prolonged: bool,
        stop_terminate_attempts: int,
        stop_terminate_interval: float,
        on_empty_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_empty_prolonged_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None, 
        on_entry_finish_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_entry_started_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_instance_stopping_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        # fmt: on
    ) -> asyncio.Task[None]:
        """
        Entry must not be running
        """
        self.ensure_not_running()

        one_time_instance: OneTimeMinecraftInstance = OneTimeMinecraftInstance(
            start_executable=self.start_executable,
        )

        self._running_instance = one_time_instance

        self._running_event.set()

        task = asyncio.create_task(
            wrap_error_logging(
                self._start(
                    empty_prolonged_minimum_streak=empty_prolonged_minimum_streak,
                    enable_empty_monitoring=enable_empty_monitoring,
                    status_check_host=status_check_host,
                    status_check_port=status_check_port,
                    status_check_protocol_version=status_check_protocol_version,
                    stop_kill_bonus_delay=stop_kill_bonus_delay,
                    stop_on_empty_prolonged=stop_on_empty_prolonged,
                    stop_terminate_attempts=stop_terminate_attempts,
                    stop_terminate_interval=stop_terminate_interval,
                    on_empty_hooks=on_empty_hooks,
                    on_empty_prolonged_hooks=on_empty_prolonged_hooks,
                    on_entry_finish_hooks=on_entry_finish_hooks,
                    on_entry_started_hooks=on_entry_started_hooks,
                    on_instance_stopping_hooks=on_instance_stopping_hooks,
                ),
                on_error_msg="Minecraft instance entry has failed with errors!",
            )
        )
        self._running_task = task

        return task

    async def _start(
        # fmt: off
        self,
        empty_prolonged_minimum_streak: int,
        enable_empty_monitoring: bool,
        status_check_host: str,
        status_check_port: int,
        status_check_protocol_version: int,
        stop_kill_bonus_delay: float,
        stop_on_empty_prolonged: bool,
        stop_terminate_attempts: int,
        stop_terminate_interval: float,

        on_empty_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_empty_prolonged_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_entry_finish_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_entry_started_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_instance_stopping_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        # fmt: on
    ) -> None:
        """
        Entry must be running
        Must be ran in a cancellable task
        Running instance must be in phase 0 of startup
        Cancelling more than once will break the internal logic

        Meant to only be used privately due to the additional logic required
        A task running this method must be cancelled in order to stop the instance
        """
        cancelled: asyncio.CancelledError | None = None

        self.ensure_running()
        one_time_instance: OneTimeMinecraftInstance = self._get_running_instance()
        one_time_instance.ensure_startup_eq_zero()
        one_time_instance.ensure_not_stopping()

        if on_entry_started_hooks is not None:
            try:
                await run_some_hooks(
                    hooks=on_entry_started_hooks,
                    msg_log_error="One-time minecraft instance entry got an error while running a started hook",
                    msg_log_cancelled="One-time minecraft instance entry got cancelled while running started hooks",
                )
            except asyncio.CancelledError as e:
                cancelled = e

        if cancelled is None:
            try:
                await one_time_instance.start(
                    empty_prolonged_minimum_streak=empty_prolonged_minimum_streak,
                    enable_empty_monitoring=enable_empty_monitoring,
                    status_check_host=status_check_host,
                    status_check_port=status_check_port,
                    status_check_protocol_version=status_check_protocol_version,
                    stop_kill_bonus_delay=stop_kill_bonus_delay,
                    stop_on_empty_prolonged=stop_on_empty_prolonged,
                    stop_terminate_attempts=stop_terminate_attempts,
                    stop_terminate_interval=stop_terminate_interval,
                    on_empty_hooks=on_empty_hooks,
                    on_empty_prolonged_hooks=on_empty_prolonged_hooks,
                    on_stopping_hooks=on_instance_stopping_hooks,
                    stdout_buffer=self._stdout_buffer,
                )
            except Exception as e:
                # TODO Should we really not propagate it?
                logging.error("Our one-time minecraft instance finished with exception(s)!", exc_info=e) # fmt: skip
            except asyncio.CancelledError as e:
                cancelled = e
                logging.info("Our one-time minecraft instance finished with a cancellation") # fmt: skip
            else:
                logging.error("Our one-time minecraft instance finished")

        if on_entry_finish_hooks is not None:
            try:
                await run_some_hooks(
                    hooks=on_entry_finish_hooks,
                    msg_log_error="One-time minecraft instance entry got an error while running a finished hook",
                    msg_log_cancelled="One-time minecraft instance entry got cancelled while running finished hooks",
                )
            except asyncio.CancelledError as e:
                cancelled = e

        self._running_event.unset()
        self._running_instance = None
        self._running_task = None

        if cancelled is not None:
            raise cancelled

    def stop(self) -> None:
        """
        Entry must be running
        Does not catch the one-time instance's state errors
        Works by cancelling the task
        """
        self.ensure_running()
        running_instance: OneTimeMinecraftInstance = self._get_running_instance()
        running_instance.stop()

    async def wait_instance_startup_phase(self, phase: int) -> None:
        """
        Entry must be running
        Waits until instance startup phase 2 OR instance stopping OR entry finished
        May raise errors if it finds out that the state is impossible waiting
        """
        running_instance: OneTimeMinecraftInstance = self._get_running_instance()

        done: Sequence[int]
        exceptions: BaseExceptionGroup | None
        cancelled: asyncio.CancelledError | None
        done, exceptions, cancelled = await coroutines_race(
            (
                running_instance.get_startup_phase().wait(phase),
                running_instance.get_stopping_event().wait(),
                self._running_event.wait_false(),
            ),
            cancel_everything_afterwards=True,
            exception_msg=f"Waiting until instance startup phase {phase}",
        )
        # 0 - startup phase
        # 1 - stopping
        # 2 - not running (finished)

        if exceptions is not None:
            raise exceptions
        if cancelled is not None:
            # Don't care
            pass

        instance_startup_phase_two: bool = 0 in done
        instance_stopping: bool = 1 in done
        entry_finished: bool = 2 in done

        # These checks won't be ran for every user of this class (because this is an optional public method), but we may at least put them here (since it's so convenient)
        if not instance_startup_phase_two:
            if instance_stopping:
                logging.info("Minecraft instance entry got stopped before entering phase two of startup") # fmt: skip
            elif entry_finished:
                raise MinecraftInstanceEntryError(
                    "Minecraft instance entry finished without stopping after creation"
                )  # fmt: skip

    async def get_status(
        self,
    ) -> mcstatus.responses.BaseStatusResponse:
        """
        Entry must be running
        Does not catch the one-time instance's state errors
        """
        self.ensure_running()
        running_instance: OneTimeMinecraftInstance = self._get_running_instance()
        return await running_instance.get_status()

    async def send_command(self, text: str) -> None:
        """
        Entry must be running
        Does not catch the one-time instance's state errors
        """
        self.ensure_running()
        running_instance: OneTimeMinecraftInstance = self._get_running_instance()
        return await running_instance.send_command(text)

    async def notify_not_empty(self) -> None:
        """
        Entry must be running
        Catches the one-time instance's state errors
        """
        self.ensure_running()
        running_instance: OneTimeMinecraftInstance = self._get_running_instance()
        try:
            await running_instance.notify_not_empty()
        except OneTimeMinecraftInstanceInvalidStateError as e:
            logging.error(f"Notified one-time minecraft instance of not emptiness and got a state error ({repr(e)})") # fmt: skip

    async def notify_empty(self) -> None:
        """
        Entry must be running
        Catches the one-time instance's state errors
        """
        self.ensure_running()
        running_instance: OneTimeMinecraftInstance = self._get_running_instance()
        try:
            await running_instance.notify_empty()
        except OneTimeMinecraftInstanceInvalidStateError as e:
            logging.error(f"Notified one-time minecraft instance of emptiness and got a state error ({repr(e)})") # fmt: skip

    # ---

    def _get_running_task(self) -> asyncio.Task[None]:
        """Entry must be running"""
        self.ensure_running()
        assert self._running_task is not None
        return self._running_task

    def _get_running_instance(self) -> OneTimeMinecraftInstance:
        """Entry must be running"""
        self.ensure_running()
        assert self._running_instance is not None
        return self._running_instance

    def get_enable_empty_monitoring(self) -> bool:
        """
        Entry must be running
        Does not catch the one-time instance's state errors
        """
        self.ensure_running()
        assert self._running_instance is not None
        return self._running_instance.get_enable_empty_monitoring()

    def get_stdout_buffer(self) -> deque[int]:
        # Useless getter for now
        return self._stdout_buffer

    # -

    def get_instance_startup_phase(self) -> IPhaseNumber:
        """Entry must be running"""
        self.ensure_running()
        running_instance: OneTimeMinecraftInstance | None = self._running_instance
        assert running_instance is not None
        return running_instance.get_startup_phase()

    def get_instance_stopping(self) -> IBooleanEvent:
        """Entry must be running"""
        self.ensure_running()
        running_instance: OneTimeMinecraftInstance | None = self._running_instance
        assert running_instance is not None
        return running_instance.get_stopping_event()

    def ensure_running(self) -> None:
        if not self._running_event.get():
            raise MinecraftInstanceEntryNotRunningError

    def ensure_not_running(self) -> None:
        if self._running_event.get():
            raise MinecraftInstanceEntryAlreadyRunningError

    def get_running(self) -> IUnsettableBooleanEvent:
        return self._running_event


async def entry_stop_featureful(entry: MinecraftInstanceEntry) -> None:
    """
    Entry must be running
    Convenience method
    Ensures startup phase 1, stops, waits for not running
    """
    entry.ensure_running()
    await entry.wait_instance_startup_phase(1)
    entry.stop()
    await entry.get_running().wait_false()


class MinecraftManagerError(MinecraftError):
    pass


class MinecraftManagerNameAlreadyTakenError(MinecraftManagerError):
    pass


class MinecraftManagerNoSuchEntryError(MinecraftManagerError):
    pass


class MinecraftManagerNoSuchEntryStartPreconfigurationError(MinecraftManagerError):
    pass


class MinecraftEntryStartPreconfiguration(TypedDict):
    """
    Allows pre setting values that are relevant only per each life of an instance (per start).
    """

    empty_prolonged_minimum_streak: Required[ReadOnly[int]]
    enable_empty_monitoring: Required[ReadOnly[bool]]
    status_check_host: Required[ReadOnly[str]]
    status_check_port: Required[ReadOnly[int]]
    status_check_protocol_version: Required[ReadOnly[int]]
    stop_kill_bonus_delay: Required[ReadOnly[float]]
    stop_on_empty_prolonged: Required[ReadOnly[bool]]
    stop_terminate_attempts: Required[ReadOnly[int]]
    stop_terminate_interval: Required[ReadOnly[float]]


def new_minecraft_entry_from_env_config(
    env_config: MinecraftEntryConfigFromEnv,
) -> MinecraftInstanceEntry:
    bytes_in_mb: int = 1048576
    return MinecraftInstanceEntry(
        name=env_config["name"],
        start_executable=env_config["start_executable"],
        estimated_max_ram_usage_bytes=bytes_in_mb
        * env_config["estimated_max_ram_usage_mb"],
        stdout_buffer_max_bytes=env_config["stdout_buffer_max_bytes"],
    )


def new_minecraft_entry_start_preconfiguration_from_env_config(
    env_config: MinecraftEntryConfigFromEnv,
) -> MinecraftEntryStartPreconfiguration:
    return MinecraftEntryStartPreconfiguration(
        empty_prolonged_minimum_streak=env_config["empty_prolonged_minimum_streak"],
        enable_empty_monitoring=env_config["enable_empty_monitoring"],
        status_check_host=env_config["status_check_host"],
        status_check_port=env_config["status_check_port"],
        status_check_protocol_version=env_config["status_check_protocol_version"],
        stop_kill_bonus_delay=env_config["stop_kill_bonus_delay"],
        stop_on_empty_prolonged=env_config["stop_on_empty_prolonged"],
        stop_terminate_attempts=env_config["stop_terminate_attempts"],
        stop_terminate_interval=env_config["stop_terminate_interval"],
    )


class MinecraftManager:
    __slots__ = (
        "empty_check_interval_s",
        "entries_by_name",
        "entries_start_preconfigurations_by_name",
        "ram_counter",
        "_emptiness_monitor",
    )

    """
    Collects minecraft instance entries
    Allows acting upon minecraft instance entries
    Keeps track of their emptiness and acts upon it
    The manager registers entries internally in lowercase, however the entries themselves store their names in any case

    All entries registered in the manager must be started by the manager. # TODO enforce this somehow?
    """
    # Ram counter may be a dummy

    empty_check_interval_s: float

    entries_by_name: MutableMapping[str, MinecraftInstanceEntry]
    entries_start_preconfigurations_by_name: MutableMapping[
        str, MinecraftEntryStartPreconfiguration
    ]
    ram_counter: IMinecraftRamCounter
    _emptiness_monitor: asyncio.Task[None] | None

    def __init__(
        self,
        empty_check_interval_s: float,
        ram_counter: IMinecraftRamCounter,
    ) -> None:
        self.empty_check_interval_s = empty_check_interval_s
        self.ram_counter = ram_counter

        self.entries_by_name = dict()
        self.entries_start_preconfigurations_by_name = dict()

    async def start(self) -> None:
        started_tasks: MutableSequence[asyncio.Task[Any]] = []
        self._emptiness_monitor = asyncio.create_task(self._start_emptiness_monitor())
        started_tasks.append(self._emptiness_monitor)
        await asyncio.wait(started_tasks, return_when=asyncio.FIRST_EXCEPTION)

    def get_entry(self, name: str) -> MinecraftInstanceEntry | None:
        name = name.lower()
        return self.entries_by_name.get(name, None)

    def get_entry_or_error(self, name: str) -> MinecraftInstanceEntry:
        name = name.lower()
        entry: MinecraftInstanceEntry | None = self.entries_by_name.get(name, None)
        if entry is None:
            raise MinecraftManagerNoSuchEntryError
        return entry

    def get_entry_start_preconfiguration(
        self, name: str
    ) -> MinecraftEntryStartPreconfiguration | None:
        name = name.lower()
        return self.entries_start_preconfigurations_by_name.get(name, None)

    def get_entry_start_preconfiguration_or_error(
        self, name: str
    ) -> MinecraftEntryStartPreconfiguration:
        name = name.lower()
        preconfiguration: MinecraftEntryStartPreconfiguration | None = (
            self.entries_start_preconfigurations_by_name.get(name, None)
        )
        if preconfiguration is None:
            raise MinecraftManagerNoSuchEntryStartPreconfigurationError
        return preconfiguration

    def get_all_entries(self) -> Sequence[MinecraftInstanceEntry]:
        return tuple(self.entries_by_name.values())

    def get_running_entries(self) -> Sequence[MinecraftInstanceEntry]:
        running_entries: Sequence[MinecraftInstanceEntry] = []
        for entry in self.entries_by_name.values():
            if entry.get_running().get():
                running_entries.append(entry)
        return running_entries

    def get_ram_counter(self) -> IReadableMinecraftRamCounter:
        return self.ram_counter

    def register(self, entry: MinecraftInstanceEntry) -> None:
        name: str = entry.name.lower()
        logging.info(f"Registering minecraft instance entry for '{name}'")
        if name in self.entries_by_name:
            raise MinecraftManagerNameAlreadyTakenError(f"Already taken {name=}")
        self.entries_by_name[name] = entry

    def register_entry_start_preconfiguration(
        self, name: str, preconfiguration: MinecraftEntryStartPreconfiguration
    ) -> None:
        name = name.lower()
        logging.info(f"Registering minecraft instance entry start preconfiguration for '{name}'") # fmt: skip
        if name in self.entries_start_preconfigurations_by_name:
            raise MinecraftManagerNameAlreadyTakenError(f"Already taken {name=}")
        self.entries_start_preconfigurations_by_name[name] = preconfiguration

    async def start_entry(
        self,
        entry: MinecraftInstanceEntry,
        empty_prolonged_minimum_streak: int,
        enable_empty_monitoring: bool,
        status_check_host: str,
        status_check_port: int,
        status_check_protocol_version: int,
        stop_kill_bonus_delay: float,
        stop_on_empty_prolonged: bool,
        stop_terminate_attempts: int,
        stop_terminate_interval: float,
        # fmt: off
        on_empty_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_empty_prolonged_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None, 
        on_entry_finish_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_entry_started_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_instance_stopping_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        # fmt: on
    ) -> None:
        """
        Entry must not be running
        Waits until instance startup phase 2 OR instance stopping OR entry finished
        Does not catch the entry's state errors
        Does not catch the one-time instance's state errors
        """
        entry.ensure_not_running()

        self.ram_counter.allocate(entry.estimated_max_ram_usage_bytes)

        async def deallocate_after_entry_finish() -> None:
            self.ram_counter.deallocate(entry.estimated_max_ram_usage_bytes)

        if on_entry_finish_hooks is None:
            on_entry_finish_hooks = (deallocate_after_entry_finish,)
        else:
            on_entry_finish_hooks = (
                deallocate_after_entry_finish,
                *on_entry_finish_hooks,
            )

        logging.info(f"Minecraft manager starting entry {entry.name=}")

        running_wait_t: asyncio.Task[Any] = asyncio.create_task(
            entry.get_running().wait()
        )
        startup_phase_2_wait_t: asyncio.Task[Any] = asyncio.create_task(
            entry.wait_instance_startup_phase(2)
        )

        # The entry saves the task as one of its attributes so we don't need to do it again here
        entry.start_as_task(
            empty_prolonged_minimum_streak=empty_prolonged_minimum_streak,
            enable_empty_monitoring=enable_empty_monitoring,
            status_check_host=status_check_host,
            status_check_port=status_check_port,
            status_check_protocol_version=status_check_protocol_version,
            stop_kill_bonus_delay=stop_kill_bonus_delay,
            stop_on_empty_prolonged=stop_on_empty_prolonged,
            stop_terminate_attempts=stop_terminate_attempts,
            stop_terminate_interval=stop_terminate_interval,
            on_empty_hooks=on_empty_hooks,
            on_empty_prolonged_hooks=on_empty_prolonged_hooks,
            on_entry_finish_hooks=on_entry_finish_hooks,
            on_entry_started_hooks=on_entry_started_hooks,
            on_instance_stopping_hooks=on_instance_stopping_hooks,
        )

        logging.info(f"Minecraft manager waiting for the entry running instance's startup phase 2 {entry.name=}") # fmt: skip
        await running_wait_t
        await startup_phase_2_wait_t
        logging.info(f"Minecraft manager finished starting entry {entry.name=}")

    async def start_entry_with_preconfiguration(
        # fmt: off
        self,
        entry: MinecraftInstanceEntry,
        preconfiguration: MinecraftEntryStartPreconfiguration,
        
        on_empty_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_empty_prolonged_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None, 
        on_entry_started_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_instance_stopping_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        on_entry_finish_hooks: Iterable[Callable[[], Coroutine[Any, Any, Any]]] | None,
        # fmt: on
    ) -> None:
        """Same contract as start entry"""
        await self.start_entry(
            entry=entry,
            # fmt: off
            empty_prolonged_minimum_streak=preconfiguration["empty_prolonged_minimum_streak"],
            enable_empty_monitoring=preconfiguration["enable_empty_monitoring"],
            status_check_host=preconfiguration["status_check_host"],
            status_check_port=preconfiguration["status_check_port"],
            status_check_protocol_version=preconfiguration["status_check_protocol_version"],
            stop_kill_bonus_delay=preconfiguration["stop_kill_bonus_delay"],
            stop_on_empty_prolonged=preconfiguration["stop_on_empty_prolonged"],
            stop_terminate_attempts=preconfiguration["stop_terminate_attempts"],
            stop_terminate_interval=preconfiguration["stop_terminate_interval"],
            # fmt: on
            on_empty_hooks=on_empty_hooks,
            on_empty_prolonged_hooks=on_empty_prolonged_hooks,
            on_entry_finish_hooks=on_entry_finish_hooks,
            on_entry_started_hooks=on_entry_started_hooks,
            on_instance_stopping_hooks=on_instance_stopping_hooks,
        )

    # For now the stopping must be done through the entry's methods directly. (this may change in the future)
    # The manager is capable of finding out when entries stop (thanks to injected hooks) so this is fine.
    # def stop_entry(self, entry: MinecraftInstanceEntry) -> None:
    #     """
    #     Entry must be running
    #     Does not catch the entry's state errors
    #     Does not catch the one-time instance's state errors
    #     Works by cancelling the task
    #     """
    #     entry.ensure_running()
    #     entry.stop()

    async def _notify_entry_empty(self, entry: MinecraftInstanceEntry) -> None:
        """
        Entry must be running
        Does not catch the entry's state errors
        Catches the one-time instance's state errors
        """
        entry.ensure_running()
        await entry.notify_empty()

    async def _notify_entry_not_empty(self, entry: MinecraftInstanceEntry) -> None:
        """
        Entry must be running
        Does not catch the entry's state errors
        Catches the one-time instance's state errors
        """
        entry.ensure_running()
        await entry.notify_not_empty()

    async def _start_emptiness_monitor(self) -> None:
        cancelled: asyncio.CancelledError | None = None

        logging.info("Starting minecraft manager emptiness monitor")
        # fmt: off
        while True:
            try:
                for entry in self.entries_by_name.values():
                    # TODO Maybe make tasks for each check and wait for them all instead of this sequential for loop
                    # But how to handle errors cleanly in that case? Hooks may be in the middle of executing, etc.
                    if not entry.get_running().get():
                        continue
                    entry_name: str = entry.name
                    try:
                        enable_empty_monitoring: bool = entry.get_enable_empty_monitoring()
                    except OneTimeMinecraftInstanceInvalidStateError as e:
                        logging.error(f"Minecraft manager emptiness monitor getting enable empty monitoring failed with invalid state error ({repr(e)}) ({entry_name=})")
                        continue

                    if not enable_empty_monitoring:
                        continue

                    logging.debug(f"Minecraft manager emptiness monitor checking status for entry | {entry_name}")
                    try:
                        # A timeout may come from out context manager or the call's internal timeout
                        async with asyncio.timeout(delay=MINECRAFT_EMPTINESS_MONITOR_STATUS_TIMEOUT_S):
                            status: mcstatus.responses.BaseStatusResponse
                            status = await entry.get_status()
                    except OneTimeMinecraftInstanceInvalidStateError as e:
                        logging.error(f"Minecraft manager emptiness monitor getting status failed with invalid state error ({repr(e)}) ({entry_name=})")
                        continue
                    except TimeoutError as e:
                        logging.warning(f"Minecraft manager emptiness monitor getting status timed out ({entry_name=})")
                        continue
                    except ConnectionRefusedError as e:
                        logging.warning("One-time minecraft instance got connection refused on status check") # fmt: skip
                        continue
                    except OSError as e:
                        # Mcstatus' OSErrors are not severe
                        logging.info(f"Minecraft manager emptiness monitor getting status failed ({entry_name=}) | {repr(e)}")
                        continue
                    except Exception as e:
                        logging.error(f"Minecraft manager emptiness monitor getting status got unknown exception ({entry_name=}) | {repr(e)}")
                        raise

                    logging.debug("Minecraft manager emptiness monitor checking players count")
                    players: int = status.players.online
                    logging.debug(f"Minecraft manager emptiness monitor got {players} players ({entry_name=})")
                    if players > 0:
                        try:
                            async with asyncio.timeout(delay=MINECRAFT_EMPTINESS_MONITOR_NOTIFY_NOT_EMPTY_TIMEOUT_S):
                                await self._notify_entry_not_empty(entry)
                        except MinecraftInstanceEntryInvalidStateError as e:
                            logging.error(f"Minecraft manager emptiness monitor notifying not empty got invalid state error ({repr(e)}) ({entry_name=})") 
                            continue
                        except TimeoutError as e:
                            # Unlike the status check, a timeout here is a bad sign so we want to log the stack trace
                            logging.error(f"Minecraft manager emptiness monitor notifying not empty timed out ({entry_name=})", exc_info=e)
                            continue
                        except Exception as e:
                            logging.error(f"Minecraft manager emptiness monitor notifying not empty failed ({repr(e)}) ({entry_name=})") 
                            continue
                    else:
                        try:
                            async with asyncio.timeout(delay=MINECRAFT_EMPTINESS_MONITOR_NOTIFY_EMPTY_TIMEOUT_S):
                                await self._notify_entry_empty(entry)
                        except MinecraftInstanceEntryInvalidStateError as e:
                            # In case getting the status took a long time
                            logging.error(f"Minecraft manager emptiness monitor notifying not empty got invalid state error ({repr(e)}) ({entry_name=})") 
                            continue
                        except TimeoutError as e:
                            # Unlike the status check, a timeout here is a bad sign so we want to log the stack trace
                            logging.error(f"Minecraft manager emptiness monitor notifying empty timed out ({entry_name=})", exc_info=e)
                            continue
                        except Exception as e:
                            logging.error(f"Minecraft manager emptiness monitor notifying empty failed ({repr(e)}) ({entry_name=})") 
                            continue

                await asyncio.sleep(self.empty_check_interval_s)
            except asyncio.CancelledError as e:
                cancelled = e
                logging.info("Minecraft manager emptiness monitor got cancelled")
                break
        # fmt: on

        logging.info("Minecraft manager emptiness monitor finished")
        # if cancelled is not None:
        raise cancelled  # it's never None currently


async def stop_ensured_many_entries(
    entries: Iterable[MinecraftInstanceEntry], timeout: float | None
) -> Iterable[MinecraftInstanceEntry]:
    """
    -> failed to stop (e.g. due to timeout), may be in various stages of stopping or not stopping at all
    Convenience
    All errors are propagated
    Stopping attempts are cancelled upon timeout
    """
    stop_tasks_of_entries: MutableMapping[asyncio.Task[Any], MinecraftInstanceEntry] = (
        {}
    )
    for entry in entries:
        stop_task: asyncio.Task[Any] = asyncio.create_task(entry_stop_featureful(entry))
        stop_tasks_of_entries[stop_task] = entry

    stop_all_coro: Coroutine[
        Any, Any, tuple[Set[asyncio.Task[Any]], Set[asyncio.Task[Any]]]
    ] = asyncio.wait(stop_tasks_of_entries.keys(), return_when=asyncio.ALL_COMPLETED)

    if timeout is None:
        await stop_all_coro
        return ()

    # Asyncio functions' automatic cancellations are actually useful for once instead of being a pain to work with

    try:
        async with asyncio.timeout(timeout):
            # This cancels the coro on its own and waits until it truly finishes (in case it catches the cancellation)
            await stop_all_coro
    except TimeoutError:
        logging.debug("Stopping ensured many entries timed out")
        pass

    timed_out_entries: Sequence[MinecraftInstanceEntry] = []
    for task, entry in stop_tasks_of_entries.items():
        # All tasks are actually done now, that's because return_when actually behaves as if it was called cancel_all_when and asyncio.wait always waits for everything to be done
        # Additionally, cancelling a done task does not affect its cancelled attribute
        # NOTE: If a task eats a CancelledError then its cancelled() will remain False, but cancelling() still increment
        if task.cancelled():
            timed_out_entries.append(entry)

    return timed_out_entries
