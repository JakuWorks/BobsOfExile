from abc import ABC, abstractmethod
from collections.abc import Sequence
import time
import logging
from typing import (
    Generic,
    TypeVar,
)
import asyncio

import zmq
import zmq.asyncio

from .hardcoded import NETWORKING_MAX_RATE_KBPS
from .async_convenience import (
    coroutines_race,
    BooleanEvent,
    IMutableBooleanEvent,
    IBooleanEvent,
    wrap_error_logging,
)

T = TypeVar("T")


class SocketDataToSend(Generic[T]):
    # This class exists because data isn't guaranteed to be sent immediately by the lazy socket
    # And may already be expired when its time comes
    __slots__ = ("_data", "_expiry_time")

    _data: T
    _expiry_time: float

    def __init__(self, data: T, expiry_time: float) -> None:
        self._data = data
        self._expiry_time = expiry_time

    def get_data(self) -> T:
        return self._data

    def get_expiry_time(self) -> float:
        return self._expiry_time

    def is_expired(self) -> bool:
        return time.time() > self._expiry_time


class ILazySocket(ABC):
    @abstractmethod
    def start(self) -> None: ...
    @abstractmethod
    async def send(self, data: SocketDataToSend[bytes]) -> None: ...
    @abstractmethod
    async def recv(self) -> bytes: ...


class LazySocketError(Exception):
    pass


class LazySocketMaintainerIsFailedError(LazySocketError):
    pass


class LazySocketNotStartedError(LazySocketError):
    pass


class LazySocketAlreadyStartedError(LazySocketError):
    pass


class LazySocket(ILazySocket):
    __slots__ = (
        "_started_event",
        "cloner",
        "_recv_queue",
        "_to_send_queue",
        "_maintainer_task",
    )

    _started_event: IMutableBooleanEvent
    cloner: "IOneTimeLazySocketCloner"
    _recv_queue: asyncio.Queue[bytes]
    _to_send_queue: asyncio.Queue[SocketDataToSend[bytes]]
    _maintainer_task: asyncio.Task[None] | None

    def __init__(self, cloner: "IOneTimeLazySocketCloner") -> None:
        self._started_event = BooleanEvent(
            set_msg="Lazy socket set as started",
            set_again_warning="Lazy socket set as started AGAIN",
        )
        self.cloner = cloner
        self._recv_queue = asyncio.Queue()
        self._to_send_queue = asyncio.Queue()
        self._maintainer_task = None

    def start(self) -> None:
        """
        Must not be started
        Starts the worker that will aim to always have at least one alive one-time lazy socket
        Must be called within a running event loop

        If a maintainer task fails, it will not be re-created
        """
        self.ensure_not_started()
        self._started_event.set()
        self._maintainer_task = asyncio.create_task(
            wrap_error_logging(
                self._start_maintainer(),
                on_error_msg="The lazy socket maintainer has failed!",
            )
        )

    async def _start_maintainer(self) -> None:
        """
        Cancelling more than once will break the internal logic
        """
        logging.info("Starting lazy socket maintainer")

        while True:
            one_time_sock: IOneTimeLazySocket = self.cloner.new()
            try:
                await one_time_sock.start(
                    recv_queue=self._recv_queue, to_send_queue=self._to_send_queue
                )
            except Exception as e:
                logging.error("Lazy socket maintainer finished with an error!", exc_info=e)  # fmt: skip
                raise
            except asyncio.CancelledError:
                logging.info("Lazy socket maintainer cancelled")
                raise

    async def send(self, data: SocketDataToSend[bytes]) -> None:
        """Must be started and not failed"""
        self.ensure_started()
        self.ensure_maintainer_not_failed()

        logging.debug("Lazy socket putting data to send")
        await self._to_send_queue.put(data)

    async def recv(self) -> bytes:
        """Must be started and not failed"""
        self.ensure_started()
        self.ensure_maintainer_not_failed()

        data: bytes = await self._recv_queue.get()
        logging.debug("Lazy socket received data")
        return data

    def is_maintainer_failed(self) -> bool:
        """Must be started"""
        self.ensure_started()
        maintainer_task: asyncio.Task[None] = self._get_maintainer_task()

        maintainer_exceptions: BaseException | None
        try:
            maintainer_exceptions = maintainer_task.exception()
        except asyncio.InvalidStateError:
            # "Exception is not set."
            maintainer_exceptions = None

        return maintainer_exceptions is not None

    def ensure_maintainer_not_failed(self) -> None:
        """Must be started"""
        self.ensure_started()
        if self.is_maintainer_failed():
            raise LazySocketMaintainerIsFailedError

    def _get_maintainer_task(self) -> asyncio.Task[None]:
        """Must be started"""
        self.ensure_started()
        assert self._maintainer_task is not None
        return self._maintainer_task

    def get_started_event(self) -> IBooleanEvent:
        return self._started_event

    def ensure_not_started(self) -> None:
        if self._started_event.get():
            raise LazySocketAlreadyStartedError

    def ensure_started(self) -> None:
        if not self._started_event.get():
            raise LazySocketNotStartedError


class IOneTimeLazySocketCloner(ABC):
    # Dependency injection provider when re-creating is needed
    @abstractmethod
    def new(self) -> "IOneTimeLazySocket": ...


class OneTimeLazySocketCloner(IOneTimeLazySocketCloner):
    __slots__ = (
        "zmq_context",
        "listening_url",
        "requesting_and_replying_url",
        "curve_key_secret",
        "curve_key_public",
        "curve_key_server",
        "is_curve_server_role",
        "heartbeat_ivl",
        "heartbeat_timeout",
    )

    zmq_context: zmq.asyncio.Context
    listening_url: str
    requesting_and_replying_url: str
    curve_key_secret: str  # Own secret key
    curve_key_public: str  # Own public key
    curve_key_server: str  # Peer's pubkey
    is_curve_server_role: bool
    heartbeat_ivl: int
    heartbeat_timeout: int

    def __init__(
        self,
        zmq_context: zmq.asyncio.Context,
        listening_url: str,
        requesting_and_replying_url: str,
        curve_key_secret: str,
        curve_key_public: str,
        curve_key_server: str,
        is_curve_server_role: bool,
        heartbeat_ivl: int,
        heartbeat_timeout: int,
    ) -> None:
        self.zmq_context = zmq_context
        self.listening_url = listening_url
        self.requesting_and_replying_url = requesting_and_replying_url
        self.curve_key_secret = curve_key_secret
        self.curve_key_public = curve_key_public
        self.curve_key_server = curve_key_server
        self.is_curve_server_role = is_curve_server_role
        self.heartbeat_ivl = heartbeat_ivl
        self.heartbeat_timeout = heartbeat_timeout

    def new(self) -> "IOneTimeLazySocket":
        return OneTimeLazySocket(
            zmq_context=self.zmq_context,
            listening_url=self.listening_url,
            requesting_and_replying_url=self.requesting_and_replying_url,
            curve_key_secret=self.curve_key_secret,
            curve_key_public=self.curve_key_public,
            curve_key_server=self.curve_key_server,
            is_curve_server_role=self.is_curve_server_role,
            heartbeat_ivl=self.heartbeat_ivl,
            heartbeat_timeout=self.heartbeat_timeout,
        )


class IOneTimeLazySocket(ABC):
    @abstractmethod
    async def start(
        self,
        recv_queue: asyncio.Queue[bytes],
        to_send_queue: asyncio.Queue[SocketDataToSend[bytes]],
    ) -> None: ...


class OneTimeLazySocket(IOneTimeLazySocket):
    """
    Once started and connected:
    Puts received messages in the asyncio queue
    Takes messages from the 'to send' queue if it's connected and tries to send them (if they are not expired). If it fails: drops them (therefore "lazy")
    Does NOT attempt to reconnect or rebind (therefore "lazy")
    The only way to properly stop the socket is by firing a disconnect event
    """

    __slots__ = (
        "zmq_context",
        "listening_url",
        "requesting_and_replying_url",
        "curve_key_secret",
        "curve_key_public",
        "curve_key_server",
        "is_curve_server_role",
        "heartbeat_ivl",
        "heartbeat_timeout",
        "_started_event",
        "_connected_event",
        "_bound_event",
        "_disconnected_event",
        "_sock",
        "_sock_monitor",
    )

    zmq_context: zmq.asyncio.Context
    listening_url: str
    requesting_and_replying_url: str
    curve_key_secret: str  # Own secret key
    curve_key_public: str  # Own public key
    curve_key_server: str  # Peer's pubkey
    is_curve_server_role: bool
    heartbeat_ivl: int
    heartbeat_timeout: int

    _started_event: IMutableBooleanEvent
    _connected_event: IMutableBooleanEvent
    _bound_event: IMutableBooleanEvent
    _disconnected_event: IMutableBooleanEvent

    _sock: zmq.asyncio.Socket
    _sock_monitor: zmq.asyncio.Socket

    def __init__(
        self,
        zmq_context: zmq.asyncio.Context,
        listening_url: str,
        requesting_and_replying_url: str,
        curve_key_secret: str,
        curve_key_public: str,
        curve_key_server: str,
        is_curve_server_role: bool,
        heartbeat_ivl: int,
        heartbeat_timeout: int,
    ) -> None:
        self.zmq_context = zmq_context
        self.listening_url = listening_url
        self.requesting_and_replying_url = requesting_and_replying_url
        self.curve_key_secret = curve_key_secret
        self.curve_key_public = curve_key_public
        self.curve_key_server = curve_key_server
        self.is_curve_server_role = is_curve_server_role
        self.heartbeat_ivl = heartbeat_ivl
        self.heartbeat_timeout = heartbeat_timeout

        self._started_event = BooleanEvent(
            set_msg="Setting one-time lazy socket as started",
            set_again_warning="Setting one-time lazy socket as started AGAIN",
        )
        self._connected_event = BooleanEvent(
            set_msg="Setting one-time lazy socket as connected",
            set_again_warning="Setting one-time lazy socket as connected AGAIN",
        )
        self._bound_event = BooleanEvent(
            set_msg="Setting one-time lazy socket as bound",
            set_again_warning="Setting one-time lazy socket as bound AGAIN",
        )
        self._disconnected_event = BooleanEvent(
            set_msg="Setting one-time lazy socket as disconnected",
            set_again_warning="Setting one-time lazy socket as disconnected AGAIN",
        )

        self._sock = self.new_socket(
            zmq_context=zmq_context,
            curve_key_secret=curve_key_secret,
            curve_key_public=curve_key_public,
            curve_key_server=curve_key_server,
            is_curve_server_role=is_curve_server_role,
            heartbeat_ivl=heartbeat_ivl,
            heartbeat_timeout=heartbeat_timeout,
        )
        self._sock_monitor = self.new_socket_monitor(self._sock)

    @classmethod
    def new_socket(
        cls,
        zmq_context: zmq.asyncio.Context,
        curve_key_secret: str,
        curve_key_public: str,
        curve_key_server: str,
        is_curve_server_role: bool,
        heartbeat_ivl: int,
        heartbeat_timeout: int,
    ) -> zmq.asyncio.Socket:
        logging.info("Creating a zmq socket for the one-time lazy socket")
        # fmt: off
        sock = zmq_context.socket(zmq.DEALER)
        sock.setsockopt_string(zmq.CURVE_PUBLICKEY, curve_key_public + "\0")
        sock.setsockopt_string(zmq.CURVE_SECRETKEY, curve_key_secret + "\0")
        if is_curve_server_role:
            sock.setsockopt(zmq.CURVE_SERVER, is_curve_server_role)
        else:
            sock.setsockopt_string(zmq.CURVE_SERVERKEY, curve_key_server + "\0")
        sock.setsockopt(zmq.HEARTBEAT_IVL, heartbeat_ivl)
        sock.setsockopt(zmq.HEARTBEAT_TIMEOUT, heartbeat_timeout)
        sock.setsockopt(zmq.SNDHWM, 1)
        sock.setsockopt(zmq.IMMEDIATE, 1) # Blocks if a send is attempted before connecting
        sock.setsockopt(zmq.LINGER, 0)
        sock.setsockopt(zmq.RATE, NETWORKING_MAX_RATE_KBPS) # Just in case something goes horribly wrong
        return sock
        #fmt: on

    @classmethod
    def new_socket_monitor(cls, sock: zmq.asyncio.Socket) -> zmq.asyncio.Socket:
        logging.info("Creating a zmq socket monitor for the one-time lazy socket")
        events: int = (
            0
            | zmq.EVENT_DISCONNECTED
            | zmq.EVENT_BIND_FAILED
            | zmq.EVENT_CONNECTED
            | zmq.EVENT_LISTENING
            | zmq.EVENT_HANDSHAKE_SUCCEEDED
        )
        sock_monitor = sock.get_monitor_socket(events=events)
        return sock_monitor

    async def start(
        self,
        recv_queue: asyncio.Queue[bytes],
        to_send_queue: asyncio.Queue[SocketDataToSend[bytes]],
    ) -> None:
        """
        Finishes blocking after the socket disconnects and all internal tasks exit
        Cancelling more than once will break the internal logic
        """
        errored: Exception | None = None
        cancelled: asyncio.CancelledError | None = None

        tasks: asyncio.TaskGroup

        try:
            async with asyncio.TaskGroup() as tasks:
                logging.info("Starting one-time lazy socket")
                tasks.create_task(self.start_sock_monitor())
                tasks.create_task(self.start_sock_receiver(recv_queue))
                tasks.create_task(self._disconnected_event.wait())

                self._sock.connect(self.requesting_and_replying_url)
                self._sock.bind(self.listening_url)
                self._started_event.set()

                done: Sequence[int]
                exceptions: BaseExceptionGroup | None
                cancelled: asyncio.CancelledError | None
                done, exceptions, cancelled = await coroutines_race(
                    (self._connected_event.wait(), self._disconnected_event.wait()),
                    cancel_everything_afterwards=True,
                    exception_msg="Exceptions in one-time lazy socket event race",
                )
                # 0 - connected
                # 1 - disconnected
                if exceptions is not None:
                    raise exceptions
                if cancelled is not None:
                    raise cancelled
                connected: bool = 0 in done
                disconnected: bool = 1 in done
                assert connected or disconnected

                if not disconnected and connected:
                    tasks.create_task(self.start_sock_sender(to_send_queue))
                    await self._disconnected_event.wait()
                else:
                    logging.warning("One-time lazy socket didn't begin sending because it was already disconnected") # fmt: skip
                # The task group context manager waits until they all finish (and closes() them automatically if any of them raises an exception/cancellation)
        except Exception as e:
            errored = e
            # Only a repr because higher level classes may be logging the error too (since we're re-raising it to them)
            logging.error(f"One-time lazy socket got exception! | {repr(e)}")
        except asyncio.CancelledError as e:
            cancelled = e
            logging.info("One-time lazy socket got cancelled")

        self._sock.close(linger=0)
        del self._sock
        self._sock_monitor.close(linger=0)
        del self._sock_monitor

        logging.info("One-time lazy socket finished")
        if errored is not None:
            raise errored
        if cancelled is not None:
            raise cancelled

    async def start_sock_sender(
        self,
        to_send_queue: asyncio.Queue[SocketDataToSend[bytes]],
    ) -> None:
        """
        Cancelling more than once will break the internal logic
        """
        errored: Exception | None = None
        cancelled: asyncio.CancelledError | None = None

        logging.info("One-time lazy socket sender started")
        while True:
            try:
                to_send: SocketDataToSend[bytes] = await to_send_queue.get()
            except asyncio.CancelledError as e:
                cancelled = e
                logging.info("One-time lazy socket got cancelled while awaiting input")
                break

            if to_send.is_expired():
                logging.info(f"One-time lazy socket cannot send the data because it is expired | {to_send.get_expiry_time()} | {to_send.get_data()}") # fmt: skip
                continue

            data: bytes = to_send.get_data()
            logging.debug(f"One-time lazy socket sending data | {data}")
            try:
                _ = await self._sock.send(data)
            except Exception as e:
                errored = e
                # TODO Specify exceptions
                to_send_queue.put_nowait(to_send)
                logging.error(f"One-time lazy socket got exception while sending (and will put back the data)") # fmt: skip
                break
            except asyncio.CancelledError as e:
                cancelled = e
                to_send_queue.put_nowait(to_send)
                logging.info("One-time lazy socket got cancelled while sending (and will put back the data)") # fmt: skip
                break

        logging.info("One-time lazy socket sender finished")
        if errored is not None:
            raise errored
        if cancelled is not None:
            raise cancelled

    async def start_sock_receiver(
        self,
        recv_queue: asyncio.Queue[bytes],
    ) -> None:
        """
        Cancelling more than once will break the internal logic
        """
        errored: Exception | None = None
        cancelled: asyncio.CancelledError | None = None

        logging.info("One-time lazy socket receiver started")
        while True:
            try:
                received: bytes = await self._sock.recv()
            except Exception as e:
                errored = e
                # TODO Specify exceptions
                logging.error("One-time lazy socket got exception while awaiting input") # fmt: skip
                break
            except asyncio.CancelledError as e:
                cancelled = e
                logging.info("One-time lazy socket receiver got cancelled while awaiting input") # fmt: skip
                break

            logging.debug(f"One-time lazy socket receiver got data | {received}")

            try:
                await recv_queue.put(received)
            except asyncio.CancelledError as e:
                cancelled = e
                logging.info("One-time lazy socket got cancelled while putting data in queue") # fmt: skip
                recv_queue.put_nowait(received)
                break

        logging.info("One-time lazy socket receiver finished")
        if errored is not None:
            raise errored
        if cancelled is not None:
            raise cancelled

    async def start_sock_monitor(self) -> None:
        """
        Cancelling more than once will break the internal logic
        """
        errored: Exception | None = None
        cancelled: asyncio.CancelledError | None = None

        logging.info("One-time lazy socket monitor started")
        while True:
            try:
                received: list[bytes] = await self._sock_monitor.recv_multipart()
            except Exception as e:
                errored = e
                # TODO Specify exceptions
                logging.error("One-time lazy socket monitor got an exception while awaiting input") # fmt: skip
                break
            except asyncio.CancelledError as e:
                cancelled = e
                logging.info("One-time lazy socket monitor got cancelled while awaiting input") # fmt: skip
                break

            if len(received) != 2:
                logging.warning("One-time lazy socket monitor event handler got an invalid event") # fmt: skip
                continue
            first_frame_b: bytes = received[0]
            first_frame_b_len: int = len(first_frame_b)
            if first_frame_b_len != 6:
                logging.warning(f"One-time lazy socket monitor event invalid first frame length {first_frame_b_len=}") # fmt: skip
                continue
            event_b: bytes = first_frame_b[:2]
            event_num: int = int.from_bytes(event_b, byteorder="little")

            logging.info(f"One-time lazy socket monitor got SOME event {event_num=}")
            match event_num:
                # Match looks better here (offers no real advantage over if..else)
                case zmq.EVENT_HANDSHAKE_SUCCEEDED:
                    logging.info("SOME event was: HANDSHAKE_SUCCEEDED")
                    self._connected_event.set()
                case zmq.EVENT_CONNECTED:
                    logging.info("SOME event was: CONNECTED")
                    # We don't actually care about this
                case zmq.EVENT_LISTENING:
                    logging.info("SOME event was: LISTENING")
                    self._bound_event.set()
                case zmq.EVENT_DISCONNECTED:
                    logging.info("SOME event was: DISCONNECTED")
                    self._disconnected_event.set()
                case zmq.EVENT_BIND_FAILED:
                    logging.info("SOME event was: BIND FAILED")
                    self._disconnected_event.set()
                case _:
                    logging.error(f"One-time lazy socket monitor got an unexpected zmq event type (and therefore ignored) {event_num=}") # fmt: skip

        logging.info("One-time lazy socket monitor finished")
        if errored is not None:
            raise errored
        if cancelled is not None:
            raise cancelled

    # ---

    def get_started(self) -> IBooleanEvent:
        return self._started_event

    def get_connected(self) -> IBooleanEvent:
        return self._connected_event

    def get_bound(self) -> IBooleanEvent:
        return self._bound_event

    def get_disconnected(self) -> IBooleanEvent:
        return self._disconnected_event
