import logging

import asyncclick as click

from .networking import NetworkingMessage
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

NAME: str = "debug_sendnetrequest"


class CommandCallDebugSendNetRequest(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
        "code",
        "timeout",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    code: int
    timeout: int

    def __init__(
        self,
        responder: IResponder,
        call_context_grand: CallContextGrand,
        code: int,
        timeout: int,
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

        self.code = code
        self.timeout = timeout

    async def call(self) -> None:
        logging.info(
            f"Sending debug net request with code {self.code=} {self.timeout=}"
        )
        msg: NetworkingMessage = NetworkingMessage(
            code=self.code,
            is_reply=False,
            id=None,
            expiration=get_future_time(self.timeout),
        )

        message: ILongResponse = self.responder.new_long_response(
            init_msg=f"Requesting with code {msg.code=} {msg.is_reply=} {msg.id=} and will time out in {self.timeout=}",
        )
        await message.start()
        response: NetworkingMessage | None = (
            await self.call_context_grand.networking_handler.request(msg=msg)
        )
        if response is None:
            logging.info("Debug net request got no response")
            await message.add_line("Timed out without a response")
        else:
            logging.info(f"Debug net request got response with code {response.code}")
            await message.add_line(
                f"Got response with {response.code=} {response.is_reply=} {response.id=}"
            )


class CommandInvocationDebugSendNetRequest(ICommandInvocationStandard):
    __slots__ = (
        "code",
        "timeout",
    )

    code: int
    timeout: int

    def __init__(self, code: int, timeout: int) -> None:
        self.code = code
        self.timeout = timeout

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallDebugSendNetRequest:
        return CommandCallDebugSendNetRequest(
            responder=responder,
            call_context_grand=call_context_grand,
            code=self.code,
            timeout=self.timeout,
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_debug_sendnetrequest(
    code: int, timeout: int
) -> CommandInvocationDebugSendNetRequest:
    return CommandInvocationDebugSendNetRequest(code=code, timeout=timeout)


def setup_cmd_debug_sendnetrequest(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_owner_permission_info()

    params: list[click.Parameter] = [
        click.Argument(["code"], type=int, required=True),
        click.Argument(["timeout"], type=int, required=False, default=10),
    ]
    command: click.Command = click.Command(
        name=NAME,
        callback=invoke_debug_sendnetrequest,
        add_help_option=False,
        params=params,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
