from dataclasses import dataclass
import logging

import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ILockingComponent,
    CommandsRegistry,
    CommandCallBase,
    CommandCallerBase,
)
from .responder import IResponder
from .permission_info import IPermissionInfo

from .power_device import PowerDeviceConnectedResponse, IPowerController

NAME: str = "testpowerdeviceconnection"


@dataclass(frozen=True, slots=True)
class CommandInvocationTestPowerDeviceConnection:
    pass


class CommandCallTestPowerDeviceConnection(
    CommandCallBase[CommandInvocationTestPowerDeviceConnection]
):
    client_power_controller: IPowerController

    def __init__(
        self,
        invocation: CommandInvocationTestPowerDeviceConnection,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        client_power_controller: IPowerController,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.client_power_controller = client_power_controller

    async def call(self) -> None:
        connected: PowerDeviceConnectedResponse | None = (
            await self.client_power_controller.get_connected()
        )
        if connected is None:
            await self.responder.respond("Failed to retrieve connection status")
            return
        await self.responder.respond(f"Connected: {connected.connected}")
        logging.info(f"Tested device connection ({connected.connected=})")


class CommandCallerTestPowerDeviceConnection(
    CommandCallerBase[CommandInvocationTestPowerDeviceConnection]
):
    client_power_controller: IPowerController

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        client_power_controller: IPowerController,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.client_power_controller = client_power_controller

    def make_invocation(
        self,
    ) -> tuple[
        "CommandCallerTestPowerDeviceConnection",
        CommandInvocationTestPowerDeviceConnection,
    ]:
        return (self, CommandInvocationTestPowerDeviceConnection())

    def make_call(
        self,
        invocation: CommandInvocationTestPowerDeviceConnection,
        responder: IResponder,
    ) -> CommandCallTestPowerDeviceConnection:
        return CommandCallTestPowerDeviceConnection(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            client_power_controller=self.client_power_controller,
        )


def setup_cmd_testpowerdeviceconnection(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    client_power_controller: IPowerController,
) -> None:
    caller: CommandCallerTestPowerDeviceConnection = (
        CommandCallerTestPowerDeviceConnection(
            locking_component=locking_component,
            permission_info=permission_info,
            client_power_controller=client_power_controller,
        )
    )

    command: click.Command = click.Command(
        name=NAME,
        callback=caller.make_invocation,
        add_help_option=False,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
    )
