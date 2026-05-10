import asyncclick as click

from .hardcoded import (
    NETCODE_REQUEST_POWER_DEVICE_STATUS,
    NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
    NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
    POWER_DEVICE_STATUS_REQUEST_TIMEOUT,
)
from .networking import NetworkingMessage
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

NAME: str = "testpowerdeviceconnectionrequest"


class CommandCallTestPowerDeviceConnectionRequest(ICommandCall):
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
        await self.responder.respond("Trying")
        msg_request: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REQUEST_POWER_DEVICE_STATUS,
            id=None,
            is_reply=False,
            expiration=get_future_time(POWER_DEVICE_STATUS_REQUEST_TIMEOUT),
        )
        reply: NetworkingMessage | None = (
            await self.call_context_grand.networking_handler.request(msg=msg_request)
        )
        if reply is None:
            await self.responder.respond("Timed out")
            return
        if reply.code == NETCODE_REPLY_POWER_DEVICE_STATUS_OK:
            await self.responder.respond(f"Got: OK ({reply.code})")
            return
        if reply.code == NETCODE_REPLY_POWER_DEVICE_STATUS_NO:
            await self.responder.respond(f"Got: NO ({reply.code})")
            return
        await self.responder.respond(f"Got unknown code ({reply.code})")


class CommandInvocationTestPowerDeviceConnectionRequest(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallTestPowerDeviceConnectionRequest:
        return CommandCallTestPowerDeviceConnectionRequest(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_testpowerdeviceconnectionrequest() -> (
    CommandInvocationTestPowerDeviceConnectionRequest
):
    return CommandInvocationTestPowerDeviceConnectionRequest()


def setup_cmd_testpowerdeviceconnectionrequest(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    command: click.Command = click.Command(
        name=NAME,
        callback=invoke_testpowerdeviceconnectionrequest,
        add_help_option=False,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
