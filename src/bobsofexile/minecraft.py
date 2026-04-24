from typing import Any, Coroutine, Callable
import logging
import pathlib
import asyncio.subprocess
import asyncio

from .data import RecentBytesBuffer

import mcstatus
import mcstatus.responses


class ServerExecutableMissingError(Exception): ...


class MinecraftInstance:
    __slots__ = (
        "stdout_buffer",
        "process",
        "started_once",
        "start_executable",
        "on_exit_async",
        "on_exit_event",
        "on_empty_async",
        "on_empty_prolonged_async",
        "empty_check_interval_s",
        "empty_prolonged_minimum_spree",
        "server_host",
        "server_port",
    )

    # Must be a valid os executable (runnable with just ./scriptpath) (so you need a shebang for linux shell scripts)
    stdout_buffer: RecentBytesBuffer
    process: asyncio.subprocess.Process | None
    started_once: bool
    start_executable: pathlib.Path
    on_exit_async: Callable[[], Coroutine[Any, Any, Any]] | None
    on_exit_event: asyncio.Event
    on_empty_async: Callable[[], Coroutine[Any, Any, Any]] | None
    on_empty_prolonged_async: Callable[[], Coroutine[Any, Any, Any]] | None
    empty_check_interval_s: int
    empty_prolonged_minimum_spree: int
    server_host: str
    server_port: int

    def __init__(
        self,
        start_executable: pathlib.Path,
        stdout_max_bytes: int,
        on_exit_async: Callable[[], Coroutine[Any, Any, Any]] | None,
        on_empty_async: Callable[[], Coroutine[Any, Any, Any]] | None,
        on_empty_prolonged_async: Callable[[], Coroutine[Any, Any, Any]],
        empty_check_interval_s: int,
        empty_prolonged_minimum_spree: int,
        server_host: str,
        server_port: int,
    ) -> None:
        logging.info(
            f"Making a new server instance | start executable: {str(start_executable)}"
        )

        self.process = None
        self.started_once = False
        self.stdout_buffer = RecentBytesBuffer(max_bytes=stdout_max_bytes)
        self.on_exit_async = on_exit_async
        self.on_exit_event = asyncio.Event()
        self.on_empty_async = on_empty_async
        self.on_empty_prolonged_async = on_empty_prolonged_async
        self.empty_check_interval_s = empty_check_interval_s
        self.empty_prolonged_minimum_spree = empty_prolonged_minimum_spree
        self.server_host = server_host
        self.server_port = server_port

        start_executable = start_executable.expanduser().resolve(strict=True).absolute()
        if not start_executable.exists():
            raise ServerExecutableMissingError("Start executable doesn't exist")
        self.start_executable = start_executable

    async def stdout_handler(
        self,
        process: asyncio.subprocess.Process,
        stdout: asyncio.StreamReader,
        stdout_buffer: RecentBytesBuffer,
    ) -> None:
        logging.info("Stdout handler started")
        while True:
            if process.returncode is not None:
                logging.debug(f"Stdout handler got return code {process.returncode}")
                break
            if self.on_exit_event.is_set():
                logging.debug("Stdout handler got exit event")
                break
            out: bytes = await stdout.read(n=100)
            if out == b"":
                logging.debug("Stdout handler got empty read")
                break
            stdout_buffer.extend(out)
        logging.info("Stdout handler finished")

    async def exit_watcher(
        self,
        process: asyncio.subprocess.Process,
        callback_async: Callable[[], Coroutine[Any, Any, Any]],
    ) -> None:
        logging.info("Exit watcher started")
        await process.wait()
        logging.info("Exit watcher detected an exit")
        await callback_async()

    async def empty_watcher(
        self,
        callback_empty: Callable[[], Coroutine[Any, Any, Any]] | None,
        callback_prolonged: Callable[[], Coroutine[Any, Any, Any]] | None,
        exit_on_prolonged: bool,
        call_empty_on_prolonged: bool,
        check_interval_s: int,
        prolonged_minimum_spree: int,
        status_checker: mcstatus.JavaServer,
    ) -> None:
        logging.info(
            f"Empty watcher started ({prolonged_minimum_spree=} {exit_on_prolonged=})"
        )
        empty_spree: int = 0
        while True:
            await asyncio.sleep(check_interval_s)

            if self.on_exit_event.is_set():
                logging.debug("Empty watcher got exit event")
                break
            try:
                status: mcstatus.responses.JavaStatusResponse = (
                    await status_checker.async_status()
                )
            except ConnectionRefusedError:
                logging.info("Connection refused on mc server status check")
                continue
            players: int = status.players.online

            # Using no guards seems to be more readable
            if players == 0:
                if self.on_exit_event.is_set():
                    logging.debug(
                        f"Empty watcher detected empty but the server already exit ({empty_spree=})"
                    )
                    break
                empty_spree += 1
                logging.debug(f"Empty watcher detected empty ({empty_spree=})")
                if empty_spree >= prolonged_minimum_spree:
                    logging.debug(
                        f"Empty watcher detected prolonged empty ({empty_spree=})"
                    )
                    if call_empty_on_prolonged:
                        if callback_empty is not None:
                            await callback_empty()
                    if callback_prolonged is not None:
                        await callback_prolonged()
                    if exit_on_prolonged:
                        break
                else:
                    if callback_empty is not None:
                        await callback_empty()
            else:
                empty_spree = 0
        logging.info("Empty watcher exit")

    def send_command(self, text: str) -> None:
        assert self.running
        assert self.process is not None
        assert self.process.stdin is not None
        text_with_enter: str = text + "\n"
        to_write: bytes = text_with_enter.encode("utf-8", errors="strict")
        self.process.stdin.write(to_write)

    @property
    def running(self) -> bool:
        return self.process is not None

    def unset_process(self) -> None:
        self.process = None

    async def start(self) -> bool:
        """-> success"""
        if self.started_once:
            raise RuntimeError("A server instance can only be started once")
        self.started_once = True

        logging.info("Starting server")
        cwd: pathlib.Path = self.start_executable.parent
        process: asyncio.subprocess.Process = (
            await asyncio.subprocess.create_subprocess_exec(
                program=self.start_executable,
                cwd=cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                text=False,
                bufsize=0,
            )
        )

        if process.stdout is None:
            process.kill()
            return False

        if process.stdin is None:
            process.kill()
            return False

        self.process = process

        async def on_exit() -> None:
            self.unset_process()
            if self.on_exit_async is not None:
                await self.on_exit_async()
            self.on_exit_event.set()

        asyncio.Task(self.exit_watcher(process=process, callback_async=on_exit))

        asyncio.Task(
            self.stdout_handler(
                process=process, stdout=process.stdout, stdout_buffer=self.stdout_buffer
            )
        )

        status_checker = mcstatus.JavaServer(
            host=self.server_host,
            port=self.server_port,
            timeout=3,
            query_port=self.server_port,
        )

        asyncio.Task(
            self.empty_watcher(
                callback_empty=self.on_empty_async,
                callback_prolonged=self.on_empty_prolonged_async,
                exit_on_prolonged=True,
                call_empty_on_prolonged=True,
                check_interval_s=self.empty_check_interval_s,
                prolonged_minimum_spree=self.empty_prolonged_minimum_spree,
                status_checker=status_checker,
            )
        )

        return True


class MinecraftContext:
    __slots__ = ("server_instance",)
    server_instance: MinecraftInstance | None

    def __init__(self) -> None:
        self.server_instance = None
