import logging

from .networking_framework import (
    NetworkingHandler,
    NetworkingMessage,
    RequestReplyContext,
)
from .hardcoded import NETCODE_REQUEST_PING, NETCODE_REPLY_PONG


class PingPongResponder:
    __slots__ = "networking_handler"

    networking_handler: NetworkingHandler

    def __init__(self, networking_handler: NetworkingHandler) -> None:
        self.networking_handler = networking_handler

    def start(self) -> None:
        # TODO Ensure starting is only done once (possibly via a convenience base class?)
        logging.info("Adding ping pong hook")
        self.networking_handler.request_replier.add_hook(
            code=NETCODE_REQUEST_PING,
            hook=self.ping_hook,
            once=False,
        )

    async def ping_hook(self, ctx: RequestReplyContext) -> None:
        logging.info("Running reply hook for ping")
        msg_pong: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_PONG,
            id=ctx.msg.id,
            is_reply=True,
            expiration=ctx.msg.expiration,
        )
        await self.networking_handler.reply(msg_pong)
