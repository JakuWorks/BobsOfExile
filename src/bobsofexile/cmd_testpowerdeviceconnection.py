import logging

import asyncclick as click

from .power_device import PowerDeviceConnectedResponse
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

NAME: str = "testpowerdeviceconnection"


class CommandCallTestPowerDeviceConnection(ICommandCall):
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
        if self.call_context_grand.client_power_controller is None:
            await self.responder.respond("No power controller")
            return
        connected: PowerDeviceConnectedResponse | None = (
            await self.call_context_grand.client_power_controller.get_connected()
        )
        if connected is None:
            await self.responder.respond("Failed to retrieve connection status")
            return
        await self.responder.respond(f"Connected: {connected.connected}")
        logging.info(f"Tested device connection ({connected.connected=})")


class CommandInvocationTestPowerDeviceConnection(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallTestPowerDeviceConnection:
        return CommandCallTestPowerDeviceConnection(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_testpowerdeviceconnection() -> CommandInvocationTestPowerDeviceConnection:
    return CommandInvocationTestPowerDeviceConnection()


def setup_cmd_testpowerdeviceconnection(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    command: click.Command = click.Command(
        name=NAME, callback=invoke_testpowerdeviceconnection, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
