import socket
import logging
import json
from typing import (
    Any,
    TypedDict,
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

import zmq
import zmq.asyncio


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


class NetworkingMessage:
    __slots__ = ("code", "id", "is_reply")

    # When replying, don't forget to set a matching ID
    KEY_CODE: Literal["code"] = "code"
    KEY_ID: Literal["id"] = "id"
    KEY_IS_REPLY: Literal["is_reply"] = "is_reply"
    code: int
    id: str
    is_reply: bool

    def __init__(self, code: int, id: str | None, is_reply: bool) -> None:
        assert (not is_reply) or (
            is_reply and code is not None
        ), "A reply cannot auto-generate IDs"

        self.code = code
        self.is_reply = is_reply

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
            }
        )

    @classmethod
    def from_json(cls, json_data: str | bytes | bytearray) -> "NetworkingMessage":
        loaded: Any = json.loads(json_data)

        if type(loaded) is not dict:
            raise InvalidNetworkingMessageStructureError("Wrong loaded type")

        #fmt: off
        code: Any = loaded.get(cls.KEY_CODE, None) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        if code is None:
            raise InvalidNetworkingMessageStructureError("Missing code")
        if type(code) is not int: # pyright: ignore[reportUnknownArgumentType]
            raise InvalidNetworkingMessageStructureError("Wrong type of code")

        id: Any = loaded.get(cls.KEY_ID, None) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] 
        if id is None:
            raise InvalidNetworkingMessageStructureError("Missing id")
        if type(id) is not str: # pyright: ignore[reportUnknownArgumentType] 
            raise InvalidNetworkingMessageStructureError("Wrong type of id")

        is_reply: Any = loaded.get(cls.KEY_IS_REPLY, None) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] 
        if is_reply is None:
            raise InvalidNetworkingMessageStructureError("Missing is_reply")
        if type(is_reply) is not bool: # pyright: ignore[reportUnknownArgumentType]
            raise InvalidNetworkingMessageStructureError("Wrong type of is_reply")
        #fmt: on

        return cls(code=code, id=id, is_reply=is_reply)


class InvalidNetworkingMessageStructureError(Exception):
    pass


# 0 - YES (up to interpretation)
# 1 - NO (up to interpretation)


class ServerReplyContext:
    pass


class NetworkingHandler:
    __slots__ = ("reply_dispatcher", "request_replier", "sock_lazy")

    reply_dispatcher: "ReplyDispatcher"
    request_replier: "RequestReplier"
    sock_lazy: "LazySocket"

    def __init__(
        self,
        reply_dispatcher: "ReplyDispatcher",
        request_replier: "RequestReplier",
        sock_lazy: "LazySocket",
    ) -> None:
        self.reply_dispatcher = reply_dispatcher
        self.request_replier = request_replier
        assert sock_lazy.started, "Socket must be started"
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
            # NOW I NEED TO HANDLE REQUESTS (NOT REPLIES) HERE TODO

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
        await self.sock_lazy.send(msg.to_json().encode("utf-8"))
        # requesting_socket.close()
        reply: NetworkingMessage | None = await self.reply_dispatcher.wait_for_reply(
            msg.id
        )
        return reply

    async def reply(self, msg: NetworkingMessage) -> None:
        await self.sock_lazy.send(msg.to_json().encode("utf-8"))


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
    """Dispatches RECEIVED replies to wake the correct listeners in the local code"""

    __slots__ = "requests"

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

    # TODO: Maybe use a generic here?
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
        return await reply_info[0](ctx)


class RequestReplierHookAlreadyExistsError(Exception):
    pass


class LazySocket:
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
        "started",
        "_first_start_event",
        "connected",
        "bound",
        "_sock",
        "recv_queue",
    )

    zmq_context: zmq.asyncio.Context
    listening_url: str
    requesting_and_replying_url: str
    curve_key_secret: str  # Own key
    curve_key_public: str  # Own key
    curve_key_server: str  # Peer's pubkey
    is_curve_server_role: bool
    heartbeat_ivl: int
    heartbeat_timeout: int

    started: bool
    _first_start_event: asyncio.Event
    connected: bool
    bound: bool  # UNUSED
    _sock: zmq.asyncio.Socket | None
    recv_queue: asyncio.Queue[bytes]

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
        self.listening_url = listening_url
        self.requesting_and_replying_url = requesting_and_replying_url
        self.zmq_context = zmq_context
        self.curve_key_public = curve_key_public
        self.curve_key_secret = curve_key_secret
        self.curve_key_server = curve_key_server
        self.is_curve_server_role = is_curve_server_role
        self.heartbeat_ivl = heartbeat_ivl
        self.heartbeat_timeout = heartbeat_timeout

        self.recv_queue = asyncio.Queue()
        self.started = False
        self.connected = False
        self.bound = False
        self._sock = None
        self._first_start_event = asyncio.Event()

    # async def recv(self) -> bytes:
    #     if not self.started:
    #         raise LazySocketNotStartedError("Not started")
    #     if not self.ready_recv:
    #         ready_recv: Iterable[zmq.asyncio.Socket] = dict(await self.recv_poller.poll(timeout=None)).keys()
    #         self.ready_recv.extend(ready_recv)
    #     assert self.ready_recv, "Ready recv is empty after polling"
    #     return await self.ready_recv.pop().recv()

    async def recv(self) -> bytes:
        if not self.started:
            raise LazySocketNotStartedError("Not started")
        received_data: bytes = await self.recv_queue.get()
        return received_data

    async def send(self, data: bytes) -> zmq.MessageTracker | None:
        if not self.started:
            raise LazySocketNotStartedError("Not started")
        if not self.connected:
            logging.info("Lazy socket sending while not connected")
            return
        logging.info("Lazy socket sending")
        assert self._sock is not None, "Connected but sock is None"
        tracker: zmq.MessageTracker | None = await self._sock.send(data)
        return tracker

    async def start(self) -> None:
        """Blocks until first start"""

        async def to_run() -> None:
            while True:
                await self.run_one_time_socket()

        asyncio.Task(to_run())
        await self._first_start_event.wait()
        self.started = True

    def new_socket(self) -> zmq.asyncio.Socket:
        # fmt: off
        sock = self.zmq_context.socket(zmq.DEALER)
        sock.setsockopt_string(zmq.CURVE_PUBLICKEY, self.curve_key_public + "\0")
        sock.setsockopt_string(zmq.CURVE_SECRETKEY, self.curve_key_secret + "\0")
        if self.is_curve_server_role:
            sock.setsockopt(zmq.CURVE_SERVER, self.is_curve_server_role)
        else:
            sock.setsockopt_string(zmq.CURVE_SERVERKEY, self.curve_key_server + "\0")
        sock.setsockopt(zmq.HEARTBEAT_IVL, self.heartbeat_ivl)
        sock.setsockopt(zmq.HEARTBEAT_TIMEOUT, self.heartbeat_timeout)
        return sock
        #fmt: on

    async def _run_sock_receiver(self, sock: zmq.asyncio.Socket) -> None:
        logging.info("Lazy socket receiver started")
        while True:
            try:
                await self.recv_queue.put(await sock.recv())
            except asyncio.CancelledError:
                logging.info("Lazy socket receiver got cancelled")
                raise

    async def run_one_time_socket(self) -> None:
        """When this function returns, the socket is already closed"""
        logging.info("Making a one-time lazy socket")
        sock: zmq.asyncio.Socket = self.new_socket()
        self._sock = sock
        events: int = (
            0
            | zmq.EVENT_DISCONNECTED
            | zmq.EVENT_BIND_FAILED
            | zmq.EVENT_CONNECTED
            | zmq.EVENT_LISTENING
            | zmq.EVENT_HANDSHAKE_SUCCEEDED
        )
        sock_monitor = sock.get_monitor_socket(events=events)
        sock_receiver: asyncio.Task[None] = asyncio.Task(self._run_sock_receiver(sock))
        sock.connect(self.requesting_and_replying_url)
        sock.bind(self.listening_url)
        if not self._first_start_event.is_set():
            self._first_start_event.set()

        while True:
            data: list[bytes] = await sock_monitor.recv_multipart()

            if len(data) != 2:
                logging.error("Socket monitor event handler got an invalid event")
                continue
            first_frame_b: bytes = data[0]
            first_frame_b_len: int = len(first_frame_b)
            if first_frame_b_len != 6:
                logging.error(
                    f"Socket monitor event invalid first frame length {first_frame_b_len=}"
                )
                continue
            event_b: bytes = first_frame_b[:2]
            event_num: int = int.from_bytes(event_b, byteorder="little")
            logging.debug(f"One time lazy socket monitor got SOME event {event_num=}")
            if event_num == zmq.EVENT_HANDSHAKE_SUCCEEDED:
                logging.info("SOME event was: HANDSHAKE_SUCCEEDED")
                self.connected = True
                continue
            if event_num == zmq.EVENT_CONNECTED:
                logging.info("SOME event was: CONNECTED")
                continue
            if event_num == zmq.EVENT_LISTENING:
                logging.info("SOME event was: LISTENING")
                self.bound = True
                continue
            if event_num == zmq.EVENT_DISCONNECTED:
                logging.info("SOME event was: DISCONNECTED")
                break
            if event_num == zmq.EVENT_BIND_FAILED:
                logging.info("SOME event was: BIND FAILED")
                break
            assert False, "Unexpected zmq event type received"

        sock_receiver.cancel()
        self.connected = False
        self.bound = False
        sock_monitor.close()
        sock.disable_monitor()
        sock.close(linger=0)
        self._sock = None


class LazySocketNotStartedError(Exception):
    pass
