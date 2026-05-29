from dataclasses import dataclass

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

from .power_device import PowerDeviceDetails, IPowerController

NAME: str = "powerstatus"


@dataclass(frozen=True, slots=True)
class CommandInvocationPowerStatus:
    pass


class CommandCallPowerStatus(CommandCallBase[CommandInvocationPowerStatus]):
    client_power_controller: IPowerController

    def __init__(
        self,
        invocation: CommandInvocationPowerStatus,
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
        details: PowerDeviceDetails | None = (
            await self.client_power_controller.get_details()
        )
        if details is None:
            await self.responder.respond("Unable to retrieve details")
            return
        status_t: str = (
            f"Connected: {details.connected}" f"\nTurned on: {details.turned_on}"
        )
        await self.responder.respond(f"Status:\n```\n{status_t}\n```")


class CommandCallerPowerStatus(CommandCallerBase[CommandInvocationPowerStatus]):
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
    ) -> tuple["CommandCallerPowerStatus", CommandInvocationPowerStatus]:
        return (self, CommandInvocationPowerStatus())

    def make_call(
        self, invocation: CommandInvocationPowerStatus, responder: IResponder
    ) -> CommandCallPowerStatus:
        return CommandCallPowerStatus(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            client_power_controller=self.client_power_controller,
        )


def setup_cmd_powerstatus(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    client_power_controller: IPowerController,
) -> None:
    caller: CommandCallerPowerStatus = CommandCallerPowerStatus(
        locking_component=locking_component,
        permission_info=permission_info,
        client_power_controller=client_power_controller,
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
