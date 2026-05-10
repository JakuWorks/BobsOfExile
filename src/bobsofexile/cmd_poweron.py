import logging
from typing import AsyncIterable

import asyncclick as click

from .hardcoded import REMOTE_POWEROFF_RETRIES, REMOTE_POWEROFF_RETRY_INTERVAL

from .power_device import PowerDeviceDetails
from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CommandsRegistry,
    CallContextGrand,
)
from .responder import IResponder, ILongResponse
from .permissions import IPermissionInfo
from .ranks import RanksRegistry

NAME: str = "poweron"


class CommandCallPoweron(ICommandCall):
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
            await self.responder.respond("Client power controller is missing. Cannot power on") # fmt: skip
            return

        # fmt: off
        msg_begin: str = "Local (client) power on results:"

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
            await self.call_context_grand.client_power_controller.get_details()
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
            self.call_context_grand.client_power_controller.power_on_async_with_retries(
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


class CommandInvocationPoweron(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallPoweron:
        return CommandCallPoweron(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return True


def invoke_poweron() -> CommandInvocationPoweron:
    return CommandInvocationPoweron()


def setup_cmd_poweron(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    command: click.Command = click.Command(
        name=NAME, callback=invoke_poweron, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
