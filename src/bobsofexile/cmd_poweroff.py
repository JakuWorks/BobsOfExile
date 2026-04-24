import logging
import time
import asyncio

import asyncclick as click

from .hardcoded import (
    POWEROFF_WAIT_TIME_SECONDS,
    NETCODE_REQUEST_POWEROFF_SOON,
    POWEROFF_REQUEST_TIMEOUT,
    MINECRAFT_STOP_COMMAND,
    POWEROFF_MINECRAFT_WAIT_TIME,
    NETCODE_REPLY_POWEROFF_SOON_NO,
    NETCODE_REPLY_POWEROFF_SOON_OK,
    POWEROFF_SAFE_POWERON_BONUS_SECONDS,
    NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
    NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
    NETCODE_REQUEST_POWER_DEVICE_STATUS,
    POWER_DEVICE_STATUS_REQUEST_TIMEOUT,
)

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond
from .networking import NetworkingMessage
from .discord_streaming_message import DiscordStreamingMessage
from .minecraft import MinecraftInstance
from .os_management import graceful_shutdown_linux

NAME: str = "poweroff"


def setup_cmd_poweroff(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_trusted_permission_info()

    callback = click.pass_context(call_cmd_poweroff)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_poweroff_raw(call_context: CallContext) -> None:
    # fmt: off
    msg_begin: str = "Power off results:"

    msg_device_test: str = "Asking the server (remote) for the device connection status..."
    msg_device_test_ok: str = "Power device connection OK"
    msg_device_test_no: str = "Power device connection NOT OK. The client WILL NOT be powered on."
    msg_device_test_timed_out: str = "Timed out without any response! The client WILL NOT be powered off."
    msg_device_test_unknown: str = "Power device connection reply is unknown and not understood by this program. The client WILL NOT be powered off."

    msg_minecraft_running: str = f"A Minecraft instance is running. Will attempt to shut it down and wait up to {POWEROFF_MINECRAFT_WAIT_TIME} seconds for it to stop..."
    msg_minecraft_not_running: str = "No Minecraft instance is running..."
    msg_minecraft_stop_ok: str = "Minecraft is stopped now..."
    msg_minecraft_stop_timed_out: str = "Minecraft did not close in the given time. Continuing poweroff..."

    msg_poweroff_request: str = f"Requesting delayed client (local) poweroff from server (remote) with a timeout of {POWEROFF_REQUEST_TIMEOUT} seconds..."
    msg_poweroff_request_timed_out: str = "Timed out without any response! The client WILL NOT be powered off.\n(note: if there was a network error that prevented us from getting the response then power supply will be cut soon even though the OS is running)"
    msg_poweroff_request_ok: str = f"Got OK from server (remote). The power WILL be cut in approximately {POWEROFF_WAIT_TIME_SECONDS} seconds."
    msg_poweroff_request_no: str = f"Got NO from server (remote). The client WILL NOT be powered off."
    msg_poweroff_request_unknown: str = f"Power off request reply is unknown and not understood by this program. The client MAY OR MAY NOT be powered off.."
    # fmt: on

    message: DiscordStreamingMessage = DiscordStreamingMessage(
        initial_content=msg_begin, command_context=call_context.young.message_context
    )
    logging.info(msg_begin)
    await message.start()

    logging.info(msg_device_test)
    await message.add_line(msg_device_test)

    device_test_msg: NetworkingMessage = NetworkingMessage(
        code=NETCODE_REQUEST_POWER_DEVICE_STATUS, id=None, is_reply=False
    )
    power_device_test_response: NetworkingMessage | None = (
        await call_context.grand.networking_handler.request(
            device_test_msg, timeout=POWER_DEVICE_STATUS_REQUEST_TIMEOUT
        )
    )
    if power_device_test_response is None:
        logging.info(msg_device_test_timed_out)
        await message.add_line(msg_device_test_timed_out)
        return
    elif power_device_test_response.code == NETCODE_REPLY_POWER_DEVICE_STATUS_NO:
        logging.info(msg_device_test_no)
        await message.add_line(msg_device_test_no)
        return
    elif power_device_test_response.code == NETCODE_REPLY_POWER_DEVICE_STATUS_OK:
        logging.info(msg_device_test_ok)
        await message.add_line(msg_device_test_ok)
    else:
        logging.info(msg_device_test_unknown)
        await message.add_line(msg_device_test_unknown)
        return

    server_instance: MinecraftInstance | None = (
        call_context.grand.minecraft_context.server_instance
    )
    if server_instance is not None:
        logging.info(msg_minecraft_running)
        await message.add_line(msg_minecraft_running)

        server_instance.send_command(MINECRAFT_STOP_COMMAND)
        try:
            await asyncio.wait_for(
                server_instance.on_exit_event.wait(),
                timeout=POWEROFF_MINECRAFT_WAIT_TIME,
            )
        except TimeoutError:
            logging.info(msg_minecraft_stop_timed_out)
            await message.add_line(msg_minecraft_stop_timed_out)
        else:
            logging.info(msg_minecraft_stop_ok)
            await message.add_line(msg_minecraft_stop_ok)
    else:
        logging.info(msg_minecraft_not_running)
        await message.add_line(msg_minecraft_not_running)

    logging.info(msg_poweroff_request)
    await message.add_line(msg_poweroff_request)

    poweroff_request: NetworkingMessage = NetworkingMessage(
        code=NETCODE_REQUEST_POWEROFF_SOON, id=None, is_reply=False
    )
    poweroff_response: NetworkingMessage | None = (
        await call_context.grand.networking_handler.request(
            poweroff_request, timeout=POWEROFF_REQUEST_TIMEOUT
        )
    )
    if poweroff_response is None:
        await message.add_line(msg_poweroff_request_timed_out)
        logging.info(msg_poweroff_request_timed_out)
        return
    elif poweroff_response.code == NETCODE_REPLY_POWEROFF_SOON_NO:
        await message.add_line(msg_poweroff_request_no)
        logging.info(msg_poweroff_request_no)
        return
    elif poweroff_response.code == NETCODE_REPLY_POWEROFF_SOON_OK:
        logging.info(msg_poweroff_request_ok)
        await message.add_line(msg_poweroff_request_ok)
    else:
        logging.info(msg_poweroff_request_unknown)
        await message.add_line(msg_poweroff_request_unknown)
        return

    # THIS ASSUMES THAT THE SERVER IS USING THE SAME WAIT TIME VALUE CONSTANT!!! (not guaranteed)
    approximate_poweroff_timestamp: int = (
        round(time.time()) + POWEROFF_WAIT_TIME_SECONDS
    )
    safe_poweron_timestamp: int = (
        approximate_poweroff_timestamp + POWEROFF_SAFE_POWERON_BONUS_SECONDS
    )

    msg_approx_poweroff_timestamp: str = (
        f"The client (local) is shutting down. Its power supply will be cut <t:{approximate_poweroff_timestamp}:R>."
        f"\nIt will be safe to power on the local bot <t:{safe_poweron_timestamp}:R>."
        "\n-# bringing back the power supply before this time will break the system in a way that will prevent it from powering on without special intervention"
    )
    await respond(call_context, content=msg_approx_poweroff_timestamp)

    logging.info("Shutting down due to bot command os poweroff request.")

    graceful_shutdown_linux()


async def call_cmd_poweroff(ctx: click.Context, /) -> None: ...


call_cmd_poweroff = simple_wrap_command_call(call_cmd_poweroff_raw, respect_lock=True)
