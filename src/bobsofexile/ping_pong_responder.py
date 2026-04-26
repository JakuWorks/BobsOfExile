import logging

from .networking import NetworkingHandler, RequestReplyContextYoung, NetworkingMessage, RequestReplyContext
from .hardcoded import NETCODE_REQUEST_PING, NETCODE_REPLY_PONG

class PingPongResponder:
    def __init__(self) -> None:
        pass

    def start(self, networking_handler: NetworkingHandler) -> None: 
        logging.info("Adding ping pong hook")
        networking_handler.request_replier.add_hook(
            code=NETCODE_REQUEST_PING,
            hook=self.ping_hook,
            once=False,
            ctx=RequestReplyContextYoung(networking_handler=networking_handler)
        )

    async def ping_hook(self, ctx: RequestReplyContext) -> None:
        logging.info("Running reply hook for ping")
        msg_pong: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_PONG,
            id=ctx.youngest.msg.id,
            is_reply=True,
            expiration=ctx.youngest.msg.expiration
        )
        await ctx.young.networking_handler.reply(msg_pong)
