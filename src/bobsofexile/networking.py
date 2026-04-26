from abc import ABC, abstractmethod
from collections.abc import Mapping, Set, Sequence
import socket
import time
import logging
import json
from typing import (
    Generic,
    Any,
    TypedDict,
    TypeVar,
    Awaitable,
    Required,
    MutableMapping,
    Literal,
    Callable,
    Coroutine,
    TypeAlias,
)
import functools
import asyncio
import uuid

from .async_convenience import wait_while_not_cancelled

import zmq
import zmq.asyncio

T = TypeVar("T")


def check_is_reachable(hostname: str) -> bool:
    try:
        host: str = socket.gethostbyname(hostname)
    except Exception:
        return False

    try:
        sock: socket.socket = socket.create_connection((host, 80), 2)
        sock.close()
    except Exception:
        return False

    return True


class NetworkingMessageDict(TypedDict):
    code: Required[int]  # Use ReadOnly if 3.12
    id: Required[str]  # Use ReadOnly if 3.12
    is_reply: Required[bool]  # Use ReadOnly if 3.12
    expiration: Required[float | int]


class NetworkingMessage:
    __slots__ = ("code", "id", "is_reply", "expiration")

    # When replying, don't forget to set a matching ID
    KEY_CODE: Literal["code"] = "code"
    KEY_ID: Literal["id"] = "id"
    KEY_IS_REPLY: Literal["is_reply"] = "is_reply"
    KEY_EXPIRATION: Literal["expiration"] = "expiration"
    code: int
    id: str
    is_reply: bool
    expiration: float | int

    def __init__(self, code: int, id: str | None, is_reply: bool, expiration: float | int) -> None:
        # Responses can just set their expiration as the request's expiration. It's not required though and isn't enforced
        assert (not is_reply) or (
            is_reply and code is not None
        ), "A reply cannot auto-generate IDs"

        self.code = code
        self.is_reply = is_reply
        self.expiration = expiration

        if id is None:
            id = str(uuid.uuid4())
        self.id = id

    def to_json(self) -> str:
        return json.dumps(self.construct_dict())

    def construct_dict(self) -> NetworkingMessageDict:
        return NetworkingMessageDict(
            {
                self.KEY_CODE: self.code,
                self.KEY_ID: self.id,
                self.KEY_IS_REPLY: self.is_reply,
                self.KEY_EXPIRATION: self.expiration
            }
        )

    @classmethod
    def from_json(cls, json_data: str | bytes | bytearray) -> "NetworkingMessage":
        loaded: Any = json.loads(json_data)

        if not isinstance(loaded, Mapping):
            raise InvalidNetworkingMessageStructureError("Wrong loaded type")

        #fmt: off
        code: Any = loaded.get(cls.KEY_CODE, None) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        if code is None:
            raise InvalidNetworkingMessageStructureError("Missing code")
        if not isinstance(code, int): # pyright: ignore[reportUnknownArgumentType]
            raise InvalidNetworkingMessageStructureError("Wrong type of code")

        id: Any = loaded.get(cls.KEY_ID, None) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] 
        if id is None:
            raise InvalidNetworkingMessageStructureError("Missing id")
        if not isinstance(id, str): # pyright: ignore[reportUnknownArgumentType] 
            raise InvalidNetworkingMessageStructureError("Wrong type of id")

        is_reply: Any = loaded.get(cls.KEY_IS_REPLY, None) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] 
        if is_reply is None:
            raise InvalidNetworkingMessageStructureError("Missing is_reply")
        if not isinstance(is_reply, bool): # pyright: ignore[reportUnknownArgumentType]
            raise InvalidNetworkingMessageStructureError("Wrong type of is_reply")
        #fmt: on

        expiration: Any = loaded.get(cls.KEY_EXPIRATION, None) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        if expiration is None:
            raise InvalidNetworkingMessageStructureError("Missing expiration")
        if not isinstance(expiration, float) and not isinstance(expiration, int):
            raise InvalidNetworkingMessageStructureError("Wrong type of expiration")

        return cls(code=code, id=id, is_reply=is_reply, expiration=expiration)


class InvalidNetworkingMessageStructureError(Exception):
    pass


class ServerReplyContext:
    pass


class NetworkingHandler:
    __slots__ = ("reply_dispatcher", "request_replier", "sock_lazy")

    reply_dispatcher: "ReplyDispatcher"
    request_replier: "RequestReplier"
    sock_lazy: "ILazySocket"

    def __init__(
        self,
        reply_dispatcher: "ReplyDispatcher",
        request_replier: "RequestReplier",
        sock_lazy: "ILazySocket",
    ) -> None:
        self.reply_dispatcher = reply_dispatcher
        self.request_replier = request_replier
        self.sock_lazy = sock_lazy

    async def start(self) -> None:
        asyncio.Task(self.start_listener())

    async def start_listener(self) -> None:
        while True:
            msg_bytes: bytes = await self.sock_lazy.recv()
            logging.info("Received SOME msg")
            try:
                as_message: NetworkingMessage = NetworkingMessage.from_json(msg_bytes)
            except InvalidNetworkingMessageStructureError:
                logging.info("SOME message had invalid structure")
                continue
            if as_message.is_reply:
                logging.info(
                    f"SOME was a reply | Code | {as_message.code} | ID | {as_message.id}"
                )
                await self.reply_dispatcher.dispatch_reply(as_message)
            else:
                logging.info(
                    f"SOME was a request | Code | {as_message.code} | ID | {as_message.id}"
                )
                request_reply_context_youngest: RequestReplyContextYoungest = (
                    RequestReplyContextYoungest(msg=as_message)
                )
                await self.request_replier.reply_to_code(
                    as_message.code, request_reply_context_youngest
                )

    async def request(
        self, msg: NetworkingMessage, timeout: float
    ) -> NetworkingMessage | None:
        # requesting_socket = self.zmq_context.socket(zmq.DEALER)
        # requesting_socket.connect(self.requesting_and_replying_url) # May raise an uncaught zmq error!
        reply_dispatcher_request: ReplyDispatcherRequest = ReplyDispatcherRequest(
            id=msg.id, reply_queue=asyncio.Queue()
        )
        await self.reply_dispatcher.setup_wait_for(
            reply_dispatcher_request, timeout=timeout
        )
        data_to_send: SocketDataToSend[bytes] = SocketDataToSend(
            data=msg.to_json().encode("utf-8"),
            expiry_time=msg.expiration
        )
        await self.sock_lazy.send(data_to_send)
        # requesting_socket.close()
        reply: NetworkingMessage | None = await self.reply_dispatcher.wait_for_reply(
            msg.id
        )
        return reply

    async def reply(self, msg: NetworkingMessage) -> None:
        data_to_send: SocketDataToSend[bytes] = SocketDataToSend(
            data=msg.to_json().encode("utf-8"),
            expiry_time=msg.expiration
        )
        await self.sock_lazy.send(data_to_send)
    

class ReplyDispatcherRequest:
    __slots__ = ("already_put_reply", "reply_queue", "id")

    already_put_reply: bool
    reply_queue: asyncio.Queue[Literal[None] | NetworkingMessage]
    id: str

    def __init__(
        self, id: str, reply_queue: asyncio.Queue[Literal[None] | NetworkingMessage]
    ) -> None:
        self.id = id
        self.reply_queue = reply_queue
        self.already_put_reply = False

    async def start_timeout(self, timeout: float) -> None:
        await asyncio.sleep(timeout)
        self.already_put_reply = True
        await self.reply_queue.put(None)

        assert self.reply_queue is not None
        # self.reply_queue.shutdown(immediate=False) # If Python 3.12


class ReplyDispatcher:
    """Dispatches RECEIVED replies to wake the correct listeners in the code"""

    __slots__ = ("requests",)

    requests: MutableMapping[str, ReplyDispatcherRequest]

    def __init__(self) -> None:
        self.requests = dict()

    async def dispatch_reply(self, reply: NetworkingMessage) -> bool:
        """-> was requested"""
        matching_request: ReplyDispatcherRequest | None = self.requests.get(
            reply.id, None
        )
        if matching_request is None:
            return False
        if matching_request.already_put_reply is True:
            raise ReplyDispatcherInvalidStateError("Request already got a reply")
        matching_request.already_put_reply = True
        await matching_request.reply_queue.put(reply)
        return True

    async def setup_wait_for(
        self, request: ReplyDispatcherRequest, timeout: float
    ) -> None:
        self.requests[request.id] = request
        asyncio.Task(request.start_timeout(timeout=timeout))

    async def wait_for_reply(
        self, sought_after_msg_id: str
    ) -> Literal[None] | NetworkingMessage:
        """Assumes the id is valid"""
        reply: Literal[None] | NetworkingMessage = await self.requests[
            sought_after_msg_id
        ].reply_queue.get()
        self.requests.pop(sought_after_msg_id)
        return reply


class ReplyDispatcherInvalidStateError(Exception):
    pass


class RequestReplyContext:
    __slots__ = ("young", "youngest")
    young: "RequestReplyContextYoung"
    youngest: "RequestReplyContextYoungest"

    def __init__(
        self,
        young: "RequestReplyContextYoung",
        youngest: "RequestReplyContextYoungest",
    ) -> None:
        self.young = young
        self.youngest = youngest


class RequestReplyContextYoung:
    __slots__ = ("networking_handler",)

    networking_handler: NetworkingHandler

    def __init__(self, networking_handler: NetworkingHandler) -> None:
        self.networking_handler = networking_handler


class RequestReplyContextYoungest:
    __slots__ = ("msg",)

    msg: NetworkingMessage

    def __init__(self, msg: NetworkingMessage) -> None:
        self.msg = msg


RequestReplyCallable: TypeAlias = Callable[
    [RequestReplyContext], Coroutine[Any, Any, Any]
]


class RequestReplier:
    __slots__ = (
        "code_hooks",
        "request_reply_context_old",
    )
    code_hooks: MutableMapping[
        int, tuple[RequestReplyCallable, RequestReplyContextYoung]
    ]

    def __init__(self) -> None:
        self.code_hooks = dict()

    def add_hook(
        self,
        code: int,
        hook: RequestReplyCallable,
        once: bool,
        ctx: RequestReplyContextYoung,
    ) -> None:
        logging.info(f"Adding request replier hook for code {code} {once=}")
        if code in self.code_hooks:
            raise RequestReplierHookAlreadyExistsError(
                f"Code already has a hook {code=}"
            )
        if once:
            hook = self._wrap_once_hook(hook=hook, code=code)
        self.code_hooks[code] = (
            hook,
            ctx,
        )

    def _wrap_once_hook(
        self, hook: RequestReplyCallable, code: int
    ) -> RequestReplyCallable:
        @functools.wraps(hook)
        async def wrapped(arg1: RequestReplyContext) -> Any:
            ret: Any = await hook(arg1)
            self.remove_hook(code=code)
            return ret

        return wrapped

    def remove_hook(self, code: int) -> None:
        if code in self.code_hooks:
            del self.code_hooks[code]

    async def reply_to_code(
        self, code: int, request_reply_context_youngest: RequestReplyContextYoungest
    ) -> Any:
        reply_info: tuple[RequestReplyCallable, RequestReplyContextYoung] | None = (
            self.code_hooks.get(code)
        )
        if reply_info is None:
            return
        ctx: RequestReplyContext = RequestReplyContext(
            young=reply_info[1],
            youngest=request_reply_context_youngest,
        )
        try:
            return await reply_info[0](ctx)
        except Exception as e:
            logging.error("Reply hook raised an exception!", exc_info=e)


class RequestReplierHookAlreadyExistsError(Exception):
    pass


class SocketDataToSend(Generic[T]):
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
    async def start(self) -> None: ...
    @abstractmethod
    async def send(self, data: SocketDataToSend[bytes]) -> None: ...
    @abstractmethod
    async def recv(self) -> bytes: ...


class LazySocketNoMaintainerError(Exception):
    pass


class LazySocket(ILazySocket):
    __slots__ = ("cloner", "_recv_queue", "_to_send_queue", "_maintainer_task")

    cloner: "IOneTimeLazySocketCloner"
    _recv_queue: asyncio.Queue[bytes]
    _to_send_queue: asyncio.Queue[SocketDataToSend[bytes]]
    _maintainer_task: asyncio.Task[None] | None

    def __init__(self, cloner: "IOneTimeLazySocketCloner") -> None:
        self.cloner = cloner
        self._recv_queue = asyncio.Queue()
        self._to_send_queue = asyncio.Queue()
        self._maintainer_task = None

    async def start(self) -> None:
        """Starts the worker that will aim to always have at least one alive one-time lazy socket"""
        self._maintainer_task = asyncio.Task(self.start_maintainer())

    async def start_maintainer(self) -> None:
        logging.info("Starting lazy socket maintainer")
        while True:
            one_time_sock: IOneTimeLazySocket = self.cloner.new()
            try:
                await one_time_sock.start(
                    recv_queue=self._recv_queue, to_send_queue=self._to_send_queue
                )
            except Exception as e:
                logging.error(
                    "Lazy socket maintainer finished with an error!", exc_info=e
                )
                raise

    async def send(self, data: SocketDataToSend[bytes]) -> None:
        logging.debug("Lazy socket putting data to send")
        if self._maintainer_task is None:
            raise LazySocketNoMaintainerError

        maintainer_exceptions: BaseException | None
        try:
            maintainer_exceptions = self._maintainer_task.exception()
        except asyncio.InvalidStateError:
            # "Exception is not set."
            maintainer_exceptions = None
        if maintainer_exceptions is not None:
            # I HATE THIS, THIS IS WRONG
            # But how else am I supposed to propagate them?
            raise maintainer_exceptions

        await self._to_send_queue.put(data)

    async def recv(self) -> bytes:
        if self._maintainer_task is None:
            raise LazySocketNoMaintainerError

        data: bytes = await self._recv_queue.get()
        logging.debug("Lazy socket received data")

        maintainer_exceptions: BaseException | None
        try:
            maintainer_exceptions = self._maintainer_task.exception()
        except asyncio.InvalidStateError:
            # "Exception is not set."
            maintainer_exceptions = None
        if maintainer_exceptions is not None:
            # I HATE THIS, THIS IS WRONG
            # But how else am I supposed to propagate them?
            raise maintainer_exceptions

        return data


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

    _started_event: asyncio.Event
    _connected_event: asyncio.Event
    _bound_event: asyncio.Event
    _disconnected_event: asyncio.Event

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

        self._started_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._bound_event = asyncio.Event()
        self._disconnected_event = asyncio.Event()

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
        Finished blocking once the socket disconnects/errors
        Propagates errors from its the spawned tasks as an exception group
        """
        logging.info("Starting one-time lazy socket")
        task_receiver: asyncio.Task[None] = asyncio.Task(
            self.start_sock_receiver(recv_queue)
        )
        task_monitor: asyncio.Task[None] = asyncio.Task(self.start_sock_monitor())
        task_sender: asyncio.Task[None] = asyncio.Task(
            self.start_sock_sender(to_send_queue)
        )
        self._sock.connect(self.requesting_and_replying_url)
        self._sock.bind(self.listening_url)
        self.set_started()

        disconnected_task: asyncio.Task[Literal[None]] = asyncio.Task(self.wait_disconnected()) # fmt: skip
        done: Set[asyncio.Task[None]]
        pending: Set[asyncio.Task[None]]
        done, pending = await asyncio.wait(
            (disconnected_task, task_receiver, task_monitor, task_sender),
            return_when=asyncio.FIRST_EXCEPTION,
        )

        self._sock.close(linger=0)
        del self._sock

        errors: Sequence[Exception] = []
        for task in done:
            try:
                exception: BaseException | None = task.exception()
            except asyncio.InvalidStateError:
                # "Exception is not set."
                continue
            if exception is not None:
                assert isinstance(exception, Exception), "Got exception of an unexpected type" # fmt: skip
                errors.append(exception)
        if errors:
            self.set_disconnected()  # A bit hacky
            raise ExceptionGroup(
                "One-time lazy socket finished with exceptions", errors
            )
        assert not pending, "Asyncio didn't complete everything?"

        logging.info("One-time lazy socket finished")

    # DON'T FORGET TO PUT DISCONNECTED CHECKS BEFORE (most) CONTINUES

    async def start_sock_sender(
        self,
        to_send_queue: asyncio.Queue[SocketDataToSend[bytes]],
    ) -> None:
        logging.info("One-time lazy socket sender initialized")
        connected_task: asyncio.Task[Literal[None]] = asyncio.Task(self.wait_connected()) # fmt: skip
        disconnected_task: asyncio.Task[Literal[None]] = asyncio.Task(self.wait_disconnected()) # fmt: skip
        done: Set[asyncio.Task[Literal[None]]]
        done, _ = await asyncio.wait(
            (connected_task, disconnected_task), return_when=asyncio.FIRST_COMPLETED
        )
        disconnected: bool = disconnected_task in done
        connected: bool = connected_task in done
        if disconnected:
            logging.warning("One-time lazy socket sender disconnected before starting")
            return
        if not connected:
            assert False, "Asyncio got nothing done?"

        logging.info("One-time lazy socket sender started")
        while True:
            to_send_resulting_task: asyncio.Task[SocketDataToSend[bytes]] = (
                asyncio.Task(to_send_queue.get())
            )

            # Inferring types due to the complex signature
            disconnected, to_send = await wait_while_not_cancelled(
                receive_waitable=to_send_resulting_task,
                cancel_waitable=disconnected_task,
                stop_receive_on_cancel=True,
            )
            if to_send is None:
                if disconnected:
                    break
                assert False, "Asyncio got nothing done?"

            if to_send.is_expired():
                logging.info(f"One-time lazy socket cannot send the data because it is expired | {to_send.get_expiry_time()} | {to_send.get_data()}") # fmt: skip
                if disconnected:
                    break
                continue
            if disconnected:
                logging.info("One-time lazy socket cannot send the data because it's disconnected") # fmt: skip
                to_send_queue.put_nowait(to_send)
                break
            logging.debug(f"One-time lazy socket sending data | {to_send.get_data()}")
            try:
                _ = await self._sock.send(to_send.get_data())
            except Exception as e:
                # TODO Specify error types properly
                logging.error(
                    f"One-time lazy socket got exception while sending | type: {type(e)} | {repr(e)}"
                )
                pass

        logging.info("One-time lazy socket sender finished")

    async def start_sock_receiver(
        self,
        recv_queue: asyncio.Queue[bytes],
    ) -> None:
        if self.get_disconnected():
            logging.warning("One-time lazy socket receiver cannot start because the socket is already disconnected") # fmt: skip
            return

        logging.info("One-time lazy socket receiver started")
        disconnected_task: asyncio.Task[None] = asyncio.Task(self.wait_disconnected())
        while True:
            recv_future: Awaitable[bytes] = self._sock.recv()
            # That's what the docstring says and their implementation returns
            assert isinstance(recv_future, asyncio.Future), "Unexpected recv future type" # fmt: skip

            # Inferring types due to the complex signature
            disconnected, received = await wait_while_not_cancelled(
                receive_waitable=recv_future,
                cancel_waitable=disconnected_task,
                stop_receive_on_cancel=True,
            )
            if received is None:
                if disconnected:
                    break
                assert False, "Asyncio got nothing done?"

            logging.debug(f"One-time lazy socket receiver got data | {received}")
            await recv_queue.put(received)
            if disconnected:
                break
        logging.info("One-time lazy socket receiver finished")

    async def start_sock_monitor(self) -> None:
        if self.get_disconnected():
            logging.warning("One-time lazy socket monitor cannot start because the socket is already disconnected") # fmt: skip
            return

        logging.info("One-time lazy socket monitor started")
        disconnected_task: asyncio.Task[None] = asyncio.Task(self.wait_disconnected())
        while True:
            recv_future: Awaitable[list[bytes]] = self._sock_monitor.recv_multipart()
            # That's what the docstring says and their implementation returns
            assert isinstance(recv_future, asyncio.Future), "Unexpected recv future type" # fmt: skip

            # Inferring types due to the complex signature
            disconnected, received = await wait_while_not_cancelled(
                receive_waitable=recv_future,
                cancel_waitable=disconnected_task,
                stop_receive_on_cancel=True,
            )
            if received is None:
                if disconnected:
                    break
                assert False, "Asyncio got nothing done?"

            if len(received) != 2:
                logging.error(
                    "One-time lazy socket monitor event handler got an invalid event"
                )
                if disconnected:
                    break
                continue
            first_frame_b: bytes = received[0]
            first_frame_b_len: int = len(first_frame_b)
            if first_frame_b_len != 6:
                logging.error(
                    f"One-time lazy socket monitor event invalid first frame length {first_frame_b_len=}"
                )
                if disconnected:
                    break
                continue
            event_b: bytes = first_frame_b[:2]
            event_num: int = int.from_bytes(event_b, byteorder="little")

            logging.info(f"One-time lazy socket monitor got SOME event {event_num=}")
            match event_num:
                case zmq.EVENT_HANDSHAKE_SUCCEEDED:
                    logging.info("SOME event was: HANDSHAKE_SUCCEEDED")
                    self.set_connected()
                case zmq.EVENT_CONNECTED:
                    logging.info("SOME event was: CONNECTED")
                    # We don't care about this
                case zmq.EVENT_LISTENING:
                    logging.info("SOME event was: LISTENING")
                    self.set_bound()
                case zmq.EVENT_DISCONNECTED:
                    logging.info("SOME event was: DISCONNECTED")
                    self.set_disconnected()
                case zmq.EVENT_BIND_FAILED:
                    logging.info("SOME event was: BIND FAILED")
                    self.set_disconnected()
                # Currently unused
                # case zmq.EVENT_CLOSED:
                #     logging.info("SOME event was: CLOSED")
                case _:
                    logging.error(
                        f"Unexpected zmq event type received by one-time lazy socket monitor (and therefore ignored) {event_num=}"
                    )
            if disconnected:
                break
        logging.info("One-time lazy socket monitor finished")

    # ----

    def set_started(self) -> None:
        if self.get_started():
            # Because it may result in unexpected behavior
            logging.warning("Setting one-time lazy socket as started AGAIN")
        else:
            logging.info("Setting one-time lazy socket as started")
            self._started_event.set()

    def get_started(self) -> bool:
        return self._started_event.is_set()

    async def wait_started(self) -> None:
        await self._started_event.wait()

    # -

    def set_connected(self) -> None:
        if self.get_connected():
            # Because it may result in unexpected behavior
            logging.warning("Setting one-time lazy socket as connected AGAIN")
        else:
            logging.info("Setting one-time lazy socket as connected")
            self._connected_event.set()

    def get_connected(self) -> bool:
        return self._connected_event.is_set()

    async def wait_connected(self) -> None:
        await self._connected_event.wait()

    # -

    def set_bound(self) -> None:
        if self.get_bound():
            # Because it may result in unexpected behavior
            logging.warning("Setting one-time lazy socket as bound AGAIN")
        else:
            logging.info("Setting one-time lazy socket as bound")
            self._bound_event.set()

    def get_bound(self) -> bool:
        return self._bound_event.is_set()

    async def wait_bound(self) -> None:
        await self._bound_event.wait()

    # -

    def set_disconnected(self) -> None:
        if self.get_disconnected():
            # Because it may result in unexpected behavior
            logging.warning("Setting one-time lazy socket as disconnected AGAIN")
        else:
            logging.info("Setting one-time lazy socket as disconnected")
            self._disconnected_event.set()

    def get_disconnected(self) -> bool:
        return self._disconnected_event.is_set()

    async def wait_disconnected(self) -> None:
        await self._disconnected_event.wait()
