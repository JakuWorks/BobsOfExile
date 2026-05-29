from dataclasses import dataclass
import asyncio
import logging

import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ILockingComponent,
    CommandsRegistry,
    CommandCallBase,
    CommandCallerBase,
)
from .responder import IResponder, ILongResponse
from .permission_info import IPermissionInfo

from .networking_framework import (
    NetworkingMessage,
    RequestReplyContext,
    NetworkingHandler,
)
from .main_convenience import get_future_time

NAME: str = "debug_setupsimplenetcodereplier"


@dataclass(frozen=True, slots=True)
class CommandInvocationDebugSetupSimpleNetCodeReplier:
    listencode: int
    replycode: int
    timeout: int


class CommandCallDebugSetupSimpleNetCodeReplier(
    CommandCallBase[CommandInvocationDebugSetupSimpleNetCodeReplier]
):
    networking_handler: NetworkingHandler

    def __init__(
        self,
        invocation: CommandInvocationDebugSetupSimpleNetCodeReplier,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        networking_handler: NetworkingHandler,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.networking_handler = networking_handler

    async def call(self) -> None:
        logging.info(f"Setting up a temporary debug net code replier {self.invocation.listencode=} {self.invocation.replycode=} {self.invocation.timeout=}") # fmt: skip

        message: ILongResponse = self.responder.new_long_response(
            init_msg=f"Setting up a temporary debug simple net code replier {self.invocation.listencode=} {self.invocation.replycode=} that will be removed after {self.invocation.timeout=}",
        )
        await message.start()

        async def reply_hook(request_reply_context: RequestReplyContext) -> None:
            received_msg: NetworkingMessage = request_reply_context.msg
            reply_msg: NetworkingMessage = NetworkingMessage(
                code=self.invocation.replycode,
                id=received_msg.id,
                is_reply=True,
                expiration=get_future_time(self.invocation.timeout),
            )

            await message.add_line(
                f"\nGot msg with {received_msg.code=} {received_msg.is_reply=} {received_msg.id=}"
                f"\nReplying to it with {reply_msg.code=} {reply_msg.is_reply=} {reply_msg.id=} "
            )
            await self.networking_handler.reply(reply_msg)

        self.networking_handler.request_replier.add_hook(
            code=self.invocation.listencode,
            hook=reply_hook,
            once=False,
        )

        await asyncio.sleep(self.invocation.timeout)

        self.networking_handler.request_replier.remove_hook(
            code=self.invocation.listencode
        )
        await message.add_line("\nRemoved the simple net code replier hook (time out)")


class CommandCallerDebugSetupSimpleNetCodeReplier(
    CommandCallerBase[CommandInvocationDebugSetupSimpleNetCodeReplier]
):
    networking_handler: NetworkingHandler

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        networking_handler: NetworkingHandler,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.networking_handler = networking_handler

    def make_invocation(self, listencode: int, replycode: int, timeout: int) -> tuple[
        "CommandCallerDebugSetupSimpleNetCodeReplier",
        CommandInvocationDebugSetupSimpleNetCodeReplier,
    ]:
        return (
            self,
            CommandInvocationDebugSetupSimpleNetCodeReplier(
                listencode=listencode, replycode=replycode, timeout=timeout
            ),
        )

    def make_call(
        self,
        invocation: CommandInvocationDebugSetupSimpleNetCodeReplier,
        responder: IResponder,
    ) -> CommandCallDebugSetupSimpleNetCodeReplier:
        return CommandCallDebugSetupSimpleNetCodeReplier(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            networking_handler=self.networking_handler,
        )


def setup_cmd_debug_setupsimplenetcodereplier(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    networking_handler: NetworkingHandler,
) -> None:
    caller: CommandCallerDebugSetupSimpleNetCodeReplier = (
        CommandCallerDebugSetupSimpleNetCodeReplier(
            locking_component=locking_component,
            permission_info=permission_info,
            networking_handler=networking_handler,
        )
    )

    params: list[click.Parameter] = [
        click.Argument(["listencode"], type=int, required=True),
        click.Argument(["replycode"], type=int, required=True),
        click.Argument(["timeout"], type=int, required=False, default=10),
    ]
    command: click.Command = click.Command(
        name=NAME,
        callback=caller.make_invocation,
        add_help_option=False,
        params=params,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
    )
