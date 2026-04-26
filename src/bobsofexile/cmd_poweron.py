import logging
from typing import AsyncIterable

import asyncclick as click

from .hardcoded import POWEROFF_RETRIES, POWEROFF_RETRY_INTERVAL

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond
from .discord_streaming_message import DiscordStreamingMessage
from .power_device import PowerDeviceDetails

NAME: str = "poweron"


def setup_cmd_poweron(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_poweron)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_poweron_raw(call_context: CallContext) -> None:
    if call_context.grand.client_power_controller is None:
        await respond(
            call_context, "Client power controller is missing. Cannot power on"
        )
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

    message: DiscordStreamingMessage = DiscordStreamingMessage(
        initial_content=msg_begin, command_context=call_context.young.message_context
    )
    logging.info(msg_begin)
    await message.start()

    details: PowerDeviceDetails | None = await call_context.grand.client_power_controller.get_details()

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
        call_context.grand.client_power_controller.power_on_async_with_retries(
            retries=POWEROFF_RETRIES, interval=POWEROFF_RETRY_INTERVAL
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
        await respond(call_context, msg_final_ok)
        logging.info(msg_final_ok_short)
    else:
        await respond(call_context, msg_final_no)
        logging.info(msg_final_no)


async def call_cmd_poweron(ctx: click.Context, /) -> None: ...


call_cmd_poweron = simple_wrap_command_call(call_cmd_poweron_raw, respect_lock=True)
