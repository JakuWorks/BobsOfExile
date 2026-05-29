from dataclasses import dataclass
import logging
from typing import AsyncIterable

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

from .hardcoded import REMOTE_POWEROFF_RETRIES, REMOTE_POWEROFF_RETRY_INTERVAL
from .power_device import PowerDeviceDetails, IPowerController

NAME: str = "poweron"


@dataclass(frozen=True, slots=True)
class CommandInvocationPoweron:
    pass


class CommandCallPoweron(CommandCallBase[CommandInvocationPoweron]):
    client_power_controller: IPowerController

    def __init__(
        self,
        invocation: CommandInvocationPoweron,
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
        # fmt: off
        msg_begin: str = "Client power on results:"

        msg_device_details: str = "Checking power device details..."
        msg_device_test_ok: str = "Power device connection OK..."
        msg_device_test_no: str = "Power device connection NOT OK... The client WILL NOT be powered on."
        msg_device_already_on_yes: str = "Device already powered on... The client ALREADY IS powered on."
        msg_device_already_on_no: str = "Device currently not powered on..."
        msg_begin_poweron_attempts: str = "Attempting power on..."

        msg_final_ok: str = (
            "Powering on client."
            "\n-# if the local bot responds to commands it means that the os has started"
        )
        msg_final_ok_short: str = "Powering on client"
        msg_final_no: str = "Failed to power on client."
        # fmt: on

        message: ILongResponse = self.responder.new_long_response(init_msg=msg_begin)
        logging.info(msg_begin)
        await message.start()

        details: PowerDeviceDetails | None = (
            await self.client_power_controller.get_details()
        )

        logging.info(msg_device_details)
        await message.add_line(msg_device_details)

        if details is None or not details.connected:
            logging.info(msg_device_test_no)
            await message.add_line(msg_device_test_no)
            return
        logging.info(msg_device_test_ok)
        await message.add_line(msg_device_test_ok)

        if details.turned_on:
            logging.info(msg_device_already_on_yes)
            await message.add_line(msg_device_already_on_yes)
            return
        logging.info(msg_device_already_on_no)
        await message.add_line(msg_device_already_on_no)

        power_on_retrier: AsyncIterable[bool] = (
            self.client_power_controller.power_on_async_with_retries(
                retries=REMOTE_POWEROFF_RETRIES, interval=REMOTE_POWEROFF_RETRY_INTERVAL
            )
        )

        logging.info(msg_begin_poweron_attempts)
        await message.add_line(msg_begin_poweron_attempts)

        i: int = 1
        final_success: bool = False
        async for success in power_on_retrier:
            msg_attempt: str = f"Attempt: {i}, Success: {success}"
            logging.info(msg_attempt)
            await message.add_line(msg_attempt)
            if success:
                final_success = True
                break
            i += 1

        if final_success:
            await self.responder.respond(msg_final_ok)
            logging.info(msg_final_ok_short)
        else:
            await self.responder.respond(msg_final_no)
            logging.info(msg_final_no)


class CommandCallerPoweron(CommandCallerBase[CommandInvocationPoweron]):
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
    ) -> tuple["CommandCallerPoweron", CommandInvocationPoweron]:
        return (self, CommandInvocationPoweron())

    def make_call(
        self, invocation: CommandInvocationPoweron, responder: IResponder
    ) -> CommandCallPoweron:
        return CommandCallPoweron(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            client_power_controller=self.client_power_controller,
        )


def setup_cmd_poweron(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    client_power_controller: IPowerController,
) -> None:
    caller: CommandCallerPoweron = CommandCallerPoweron(
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
