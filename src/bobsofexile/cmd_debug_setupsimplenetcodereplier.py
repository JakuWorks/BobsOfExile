import logging
import asyncio

import asyncclick as click

from .networking import NetworkingMessage, RequestReplyContext, RequestReplyContextYoung
from .main_convenience import get_future_time
from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CallContextGrand,
    CommandsRegistry,
)
from .responder import IResponder, ILongResponse
from .permissions import IPermissionInfo
from .ranks import RanksRegistry

NAME: str = "debug_setupsimplenetcodereplier"


class CommandCallDebugSetupSimpleNetCodeReplier(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
        "listencode",
        "replycode",
        "timeout",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    listencode: int
    replycode: int
    timeout: int

    def __init__(
        self,
        responder: IResponder,
        call_context_grand: CallContextGrand,
        listencode: int,
        replycode: int,
        timeout: int,
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

        self.listencode = listencode
        self.replycode = replycode
        self.timeout = timeout

    async def call(self) -> None:
        logging.info(
            f"Setting up a temporary debug net code replier {self.listencode=} {self.replycode=} {self.timeout=}" # fmt: skip
        )

        message: ILongResponse = self.responder.new_long_response(
            init_msg=f"Setting up a temporary debug simple net code replier {self.listencode=} {self.replycode=} that will be removed after {self.timeout=}",
        )
        await message.start()

        async def reply_hook(request_reply_context: RequestReplyContext) -> None:
            received_msg: NetworkingMessage = request_reply_context.youngest.msg
            reply_msg: NetworkingMessage = NetworkingMessage(
                code=self.replycode,
                id=received_msg.id,
                is_reply=True,
                expiration=get_future_time(self.timeout),
            )

            await message.add_line(
                f"\nGot msg with {received_msg.code=} {received_msg.is_reply=} {received_msg.id=}"
                f"\nReplying to it with {reply_msg.code=} {reply_msg.is_reply=} {reply_msg.id=} "
            )
            await request_reply_context.young.networking_handler.reply(reply_msg)

        request_reply_context_young: RequestReplyContextYoung = (
            RequestReplyContextYoung(
                networking_handler=self.call_context_grand.networking_handler
            )
        )
        self.call_context_grand.networking_handler.request_replier.add_hook(
            code=self.listencode,
            hook=reply_hook,
            once=False,
            ctx=request_reply_context_young,
        )

        await asyncio.sleep(self.timeout)

        self.call_context_grand.networking_handler.request_replier.remove_hook(
            code=self.listencode
        )
        await message.add_line("\nRemoved the simple net code replier hook (time out)")


class CommandInvocationDebugSetupSimpleNetCodeReplier(ICommandInvocationStandard):
    __slots__ = (
        "listencode",
        "replycode",
        "timeout",
    )

    listencode: int
    replycode: int
    timeout: int

    def __init__(self, listencode: int, replycode: int, timeout: int) -> None:
        listencode = listencode
        replycode = replycode
        timeout = timeout

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallDebugSetupSimpleNetCodeReplier:
        return CommandCallDebugSetupSimpleNetCodeReplier(
            responder=responder,
            call_context_grand=call_context_grand,
            listencode=self.listencode,
            replycode=self.replycode,
            timeout=self.timeout,
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_debug_setupsimplenetcodereplier(
    listencode: int, replycode: int, timeout: int
) -> CommandInvocationDebugSetupSimpleNetCodeReplier:
    return CommandInvocationDebugSetupSimpleNetCodeReplier(
        listencode=listencode, replycode=replycode, timeout=timeout
    )


def setup_cmd_debug_setupsimplenetcodereplier(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_owner_permission_info()

    params: list[click.Parameter] = [
        click.Argument(["listencode"], type=int, required=True),
        click.Argument(["replycode"], type=int, required=True),
        click.Argument(["timeout"], type=int, required=False, default=10),
    ]
    command: click.Command = click.Command(
        name=NAME,
        callback=invoke_debug_setupsimplenetcodereplier,
        add_help_option=False,
        params=params,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
