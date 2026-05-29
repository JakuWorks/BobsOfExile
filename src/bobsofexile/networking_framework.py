from collections.abc import Mapping
import time
import logging
import json
from typing_extensions import ReadOnly
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

from .main_convenience import ensure_existence_and_type
from .networking_socket import ILazySocket, SocketDataToSend


class NetworkingFrameworkError(Exception):
    pass


class NetworkingFrameworkProtocolError(NetworkingFrameworkError):
    pass


class NetworkingFrameworkInvalidStateError(NetworkingFrameworkError):
    pass


class NetworkingFrameworkUsageError(NetworkingFrameworkError):
    pass


class NetworkingMessageDict(TypedDict):
    code: ReadOnly[Required[int]]
    id: ReadOnly[Required[str]]
    is_reply: ReadOnly[Required[bool]]
    expiration: ReadOnly[Required[float | int]]


class NetworkingMessageInvalidStructureError(NetworkingFrameworkProtocolError):
    pass


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
    expiration: float

    def __init__(
        self, code: int, id: str | None, is_reply: bool, expiration: float
    ) -> None:
        """
        The ID may be automatically generated for requests
        """
        # Most of the time, responses can just set their expiration as the request's expiration. It's not required though and isn't enforced

        if is_reply and id is None:
            raise NetworkingFrameworkUsageError("A reply must specify an ID")

        self.code = code
        self.is_reply = is_reply
        self.expiration = expiration

        if id is None:
            self.id = str(uuid.uuid4())
        else:
            self.id = id

    def to_json(self) -> str:
        return json.dumps(self.construct_dict())

    def construct_dict(self) -> NetworkingMessageDict:
        return NetworkingMessageDict(
            {
                self.KEY_CODE: self.code,
                self.KEY_ID: self.id,
                self.KEY_IS_REPLY: self.is_reply,
                self.KEY_EXPIRATION: self.expiration,
            }
        )

    def is_expired(self) -> bool:
        return time.time() > self.expiration


def networking_message_from_json(
    json_data: str | bytes | bytearray,
) -> "NetworkingMessage":
    loaded_raw: Any = json.loads(json_data)
    loaded: Mapping[Any, Any] = ensure_existence_and_type('loaded data', Mapping, loaded_raw,                              NetworkingMessageInvalidStructureError, NetworkingMessageInvalidStructureError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    code: int = ensure_existence_and_type('code', int, loaded.get(NetworkingMessage.KEY_CODE, None),                       NetworkingMessageInvalidStructureError, NetworkingMessageInvalidStructureError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    id: str = ensure_existence_and_type('id', str, loaded.get(NetworkingMessage.KEY_ID, None),                             NetworkingMessageInvalidStructureError, NetworkingMessageInvalidStructureError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    is_reply: int = ensure_existence_and_type('is_reply', bool, loaded.get(NetworkingMessage.KEY_IS_REPLY, None),          NetworkingMessageInvalidStructureError, NetworkingMessageInvalidStructureError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    expiration: float = ensure_existence_and_type('expiration', float, loaded.get(NetworkingMessage.KEY_EXPIRATION, None), NetworkingMessageInvalidStructureError, NetworkingMessageInvalidStructureError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    return NetworkingMessage(code=code, id=id, is_reply=is_reply, expiration=expiration)


class RequestReplyContext:
    __slots__ = ("msg",)

    msg: NetworkingMessage

    def __init__(self, msg: NetworkingMessage) -> None:
        self.msg = msg


RequestReplyCallable: TypeAlias = Callable[
    [RequestReplyContext], Coroutine[Any, Any, Any]
]


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


class ReplyDispatcherInvalidStateError(NetworkingFrameworkInvalidStateError):
    pass


class RequestReplierHookAlreadyExistsError(NetworkingFrameworkUsageError):
    pass


class RequestReplier:
    __slots__ = ("code_hooks",)

    code_hooks: MutableMapping[int, RequestReplyCallable]

    def __init__(self) -> None:
        self.code_hooks = dict()

    def add_hook(
        self,
        code: int,
        hook: RequestReplyCallable,
        once: bool,
    ) -> None:
        logging.info(f"Adding request replier hook for code {code} {once=}")
        if code in self.code_hooks:
            raise RequestReplierHookAlreadyExistsError(f"Code already has a hook {code=}") # fmt: skip
        if once:
            hook = self._wrap_once_hook(hook=hook, code_to_remove=code)
        self.code_hooks[code] = hook

    def _wrap_once_hook(
        self, hook: RequestReplyCallable, code_to_remove: int
    ) -> RequestReplyCallable:
        @functools.wraps(hook)
        async def wrapped(arg1: RequestReplyContext) -> Any:
            ret: Any = await hook(arg1)
            self.remove_hook(code=code_to_remove)
            return ret

        return wrapped

    def remove_hook(self, code: int) -> None:
        if code in self.code_hooks:
            del self.code_hooks[code]

    async def reply_to_code(
        self, code: int, request_reply_context: RequestReplyContext
    ) -> Any:
        hook: RequestReplyCallable | None = self.code_hooks.get(code, None)
        if hook is None:
            return

        try:
            return await hook(request_reply_context)
        except Exception as e:
            logging.error("Reply hook raised an exception!", exc_info=e)


class NetworkingHandler:
    __slots__ = ("reply_dispatcher", "request_replier", "sock_lazy")

    reply_dispatcher: ReplyDispatcher
    request_replier: RequestReplier
    sock_lazy: ILazySocket

    def __init__(
        self,
        reply_dispatcher: ReplyDispatcher,
        request_replier: RequestReplier,
        sock_lazy: ILazySocket,
    ) -> None:
        self.reply_dispatcher = reply_dispatcher
        self.request_replier = request_replier
        self.sock_lazy = sock_lazy

    async def start(self) -> None:
        """Blocks until all tasks finish (forever)"""
        await self.start_listener()

    async def start_listener(self) -> None:
        while True:
            msg_bytes: bytes = await self.sock_lazy.recv()
            logging.info("Received SOME msg")
            try:
                as_message: NetworkingMessage = networking_message_from_json(msg_bytes)
            except NetworkingMessageInvalidStructureError:
                logging.info("SOME message had invalid structure")
                continue

            if as_message.is_reply:
                logging.info(f"SOME was a reply | Code | {as_message.code} | ID | {as_message.id} | Expiration {as_message.expiration}") # fmt: skip
                if as_message.is_expired():
                    logging.info("SOME was already expired (and therefore ignored)")
                    continue
                await self.reply_dispatcher.dispatch_reply(as_message)

            else:
                logging.info(f"SOME was a request | Code | {as_message.code} | ID | {as_message.id} | Expiration {as_message.expiration}") # fmt: skip
                if time.time() > as_message.expiration:
                    logging.info("SOME was already expired")
                    continue
                request_reply_context: RequestReplyContext = RequestReplyContext(
                    msg=as_message
                )
                await self.request_replier.reply_to_code(
                    as_message.code, request_reply_context
                )

    async def request(self, msg: NetworkingMessage) -> NetworkingMessage | None:
        reply_dispatcher_request: ReplyDispatcherRequest = ReplyDispatcherRequest(
            id=msg.id, reply_queue=asyncio.Queue()
        )

        timeout: float = max(0, msg.expiration - time.time())
        await self.reply_dispatcher.setup_wait_for(
            reply_dispatcher_request, timeout=timeout
        )

        data_to_send: SocketDataToSend[bytes] = SocketDataToSend(
            data=msg.to_json().encode("utf-8"), expiry_time=msg.expiration
        )
        await self.sock_lazy.send(data_to_send)
        reply: NetworkingMessage | None = await self.reply_dispatcher.wait_for_reply(
            msg.id
        )
        return reply

    async def reply(self, msg: NetworkingMessage) -> None:
        data_to_send: SocketDataToSend[bytes] = SocketDataToSend(
            data=msg.to_json().encode("utf-8"), expiry_time=msg.expiration
        )
        await self.sock_lazy.send(data_to_send)
