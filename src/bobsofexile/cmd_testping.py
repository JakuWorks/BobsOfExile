import asyncclick as click

from .networking import NetworkingMessage
from .hardcoded import TESTPING_TIMEOUT, NETCODE_REQUEST_PING
from .main_convenience import get_future_time
from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CommandsRegistry,
    CallContextGrand,
)
from .responder import IResponder
from .permissions import IPermissionInfo
from .ranks import RanksRegistry

NAME: str = "testping"


class CommandCallTestPing(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    def __init__(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

    async def call(self) -> None:
        request_ping_msg: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REQUEST_PING,
            is_reply=False,
            expiration=get_future_time(after_seconds=TESTPING_TIMEOUT),
            id=None,
        )
        response: NetworkingMessage | None = (
            await self.call_context_grand.networking_handler.request(request_ping_msg)
        )
        if response:
            await self.responder.respond("Pong!")
        else:
            await self.responder.respond("Timed out.")


class CommandInvocationTestPing(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallTestPing:
        return CommandCallTestPing(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_testping() -> CommandInvocationTestPing:
    return CommandInvocationTestPing()


def setup_cmd_testping(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    command: click.Command = click.Command(
        name=NAME, callback=invoke_testping, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
