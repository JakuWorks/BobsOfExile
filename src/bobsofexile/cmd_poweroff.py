import logging
import time
from collections.abc import Sequence

import asyncclick as click

from .hardcoded import (
    POWEROFF_WAIT_TIME_SECONDS,
    NETCODE_REQUEST_POWEROFF_SOON,
    POWEROFF_REQUEST_TIMEOUT,
    POWEROFF_MINECRAFT_WAIT_TIME,
    NETCODE_REPLY_POWEROFF_SOON_NO,
    NETCODE_REPLY_POWEROFF_SOON_OK,
    POWEROFF_SAFE_POWERON_BONUS_SECONDS,
    NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
    NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
    NETCODE_REQUEST_POWER_DEVICE_STATUS,
    POWER_DEVICE_STATUS_REQUEST_TIMEOUT,
)

from .networking import NetworkingMessage
from .minecraft import MinecraftInstanceEntry, stop_ensured_many_entries
from .os_management import graceful_shutdown_linux
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

NAME: str = "poweroff"


class CommandCallPoweroff(ICommandCall):
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
        # fmt: off
        msg_begin: str = "Power off results:"

        msg_device_test: str = f"Asking the server (remote) for the device status with a timeout of {POWER_DEVICE_STATUS_REQUEST_TIMEOUT} seconds..."
        msg_device_test_ok: str = "Power device connection OK..."
        msg_device_test_no: str = "Power device connection NOT OK... The client WILL NOT be powered off."
        msg_device_test_timed_out: str = "Timed out without any response... The client WILL NOT be powered off."
        msg_device_test_unknown: str = "Power device connection reply is unknown and not understood by this program... The client WILL NOT be powered off."

        msg_minecraft_not_running: str = "No Minecraft instances are running..."
        msg_minecraft_running_format: str = "There are {} running minecraft instances. Will attempt to stop them and wait up to "+f"{POWEROFF_MINECRAFT_WAIT_TIME} seconds for them to stop..."
        msg_minecraft_stop_exceptions_format: str = "Minecraft instances raised exceptions while stopping (there may be more in the logs): {}"
        msg_minecraft_stop_timed_out_format: str = "{} minecraft instances are still stopping (and not errored). Continuing poweroff..."
        msg_minecraft_stop_ok: str = "All minecraft instances are stopped now..."

        msg_poweroff_request: str = f"Requesting delayed client (local) poweroff from server (remote) with a timeout of {POWEROFF_REQUEST_TIMEOUT} seconds..."
        msg_poweroff_request_timed_out: str = "Timed out without any response! The client WILL NOT be powered off.\n(note: if there was a network error that prevented us from getting the response then power supply will be cut soon even though the OS is running)"
        msg_poweroff_request_ok: str = f"Got OK from server (remote). The power WILL be cut in approximately {POWEROFF_WAIT_TIME_SECONDS} seconds."
        msg_poweroff_request_no: str = f"Got NO from server (remote). The client WILL NOT be powered off."
        msg_poweroff_request_unknown: str = f"Power off request's reply is unknown and not understood by this program... The client MAY OR MAY NOT be powered off."
        # fmt: on

        if self.call_context_grand.minecraft_manager is None:
            await self.responder.respond(
                "There is no minecraft manager, cannot proceed."
            )
            # Poweroff is client-only so this indicates a bug (I'd rather have it fail early)
            return

        message: ILongResponse = self.responder.new_long_response(init_msg=msg_begin)
        logging.info(msg_begin)
        await message.start()

        logging.info(msg_device_test)
        await message.add_line(msg_device_test)

        device_test_msg: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REQUEST_POWER_DEVICE_STATUS,
            id=None,
            is_reply=False,
            expiration=get_future_time(POWER_DEVICE_STATUS_REQUEST_TIMEOUT),
        )
        power_device_test_response: NetworkingMessage | None = (
            await self.call_context_grand.networking_handler.request(device_test_msg)
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

        running_entries: Sequence[MinecraftInstanceEntry] = (
            self.call_context_grand.minecraft_manager.get_running_entries()
        )
        if running_entries:
            # fmt: off
            msg_minecraft_running: str = msg_minecraft_running_format.format(str(len(running_entries)))
            await message.add_line(msg_minecraft_running)
            logging.info(msg_minecraft_running)
            
            # erroring counts as stopping
            stopping_exceptions: Exception | None = None
            failed_to_stop: Sequence[MinecraftInstanceEntry] | None = None
            try:
                failed_to_stop = list(await stop_ensured_many_entries(running_entries, timeout=POWEROFF_MINECRAFT_WAIT_TIME))
            except Exception as e:
                stopping_exceptions = e

            failed_to_stop_count: int | None
            if failed_to_stop is None:
                failed_to_stop_count = None
            else:
                failed_to_stop_count = len(failed_to_stop)

            if stopping_exceptions is not None:
                msg_minecraft_stopping_exceptions: str = msg_minecraft_stop_exceptions_format.format(repr(stopping_exceptions))
                logging.info(msg_minecraft_stopping_exceptions)
                await message.add_line(msg_minecraft_stopping_exceptions)
            if failed_to_stop_count == 0:
                logging.info(msg_minecraft_stop_ok)
                await message.add_line(msg_minecraft_stop_ok)
            else:
                msg_minecraft_stop_timed_out: str = msg_minecraft_stop_timed_out_format.format(str(failed_to_stop_count))
                logging.info(msg_minecraft_stop_timed_out)
                await message.add_line(msg_minecraft_stop_timed_out)
        else:
            logging.info(msg_minecraft_not_running)
            await message.add_line(msg_minecraft_not_running)
        # fmt: on

        logging.info(msg_poweroff_request)
        await message.add_line(msg_poweroff_request)

        poweroff_request: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REQUEST_POWEROFF_SOON,
            id=None,
            is_reply=False,
            expiration=get_future_time(POWEROFF_REQUEST_TIMEOUT),
        )
        poweroff_response: NetworkingMessage | None = (
            await self.call_context_grand.networking_handler.request(poweroff_request)
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
            "\n-# bringing back the power supply before this time will break the power state"
        )
        await self.responder.respond(msg_approx_poweroff_timestamp)

        logging.info("Shutting down due to bot command os poweroff request.")

        graceful_shutdown_linux()


class CommandInvocationPoweroff(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallPoweroff:
        return CommandCallPoweroff(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return True


def invoke_poweroff() -> CommandInvocationPoweroff:
    return CommandInvocationPoweroff()


def setup_cmd_poweroff(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_trusted_permission_info()

    command: click.Command = click.Command(
        name=NAME, callback=invoke_poweroff, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
