from dataclasses import dataclass
import logging
import time
from collections.abc import Sequence

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
from .networking_framework import NetworkingMessage, NetworkingHandler
from .minecraft import (
    MinecraftInstanceEntry,
    stop_ensured_many_entries,
    MinecraftManager,
)
from .os_management import graceful_shutdown_linux
from .main_convenience import get_future_time

NAME: str = "poweroff"


@dataclass(frozen=True, slots=True)
class CommandInvocationPoweroff:
    only_shutdown: bool


class CommandCallPoweroff(CommandCallBase[CommandInvocationPoweroff]):
    minecraft_manager: MinecraftManager
    networking_handler: NetworkingHandler

    def __init__(
        self,
        invocation: CommandInvocationPoweroff,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        minecraft_manager: MinecraftManager,
        networking_handler: NetworkingHandler,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.minecraft_manager = minecraft_manager
        self.networking_handler = networking_handler

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
        msg_poweroff_request_no_only_shutdown: str = "No attempts to request a delayed client poweroff from server or notify a power controller have been made due to the only shutdown mode."
        msg_poweroff_request_unknown: str = f"Power off request's reply is unknown and not understood by this program... The client MAY OR MAY NOT be powered off."

        msg_poweroff_ok_only_shutdown: str = "The client's OS will shut down now."
        # fmt: on

        message: ILongResponse = self.responder.new_long_response(init_msg=msg_begin)
        logging.info(msg_begin)
        await message.start()

        if not self.invocation.only_shutdown:
            logging.info(msg_device_test)
            await message.add_line(msg_device_test)

            device_test_msg: NetworkingMessage = NetworkingMessage(
                code=NETCODE_REQUEST_POWER_DEVICE_STATUS,
                id=None,
                is_reply=False,
                expiration=get_future_time(POWER_DEVICE_STATUS_REQUEST_TIMEOUT),
            )
            power_device_test_response: NetworkingMessage | None = (
                await self.networking_handler.request(device_test_msg)
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
        else:
            # No message for this case
            pass

        running_entries: Sequence[MinecraftInstanceEntry] = (
            self.minecraft_manager.get_running_entries()
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

        if not self.invocation.only_shutdown:
            logging.info(msg_poweroff_request)
            await message.add_line(msg_poweroff_request)

            poweroff_request: NetworkingMessage = NetworkingMessage(
                code=NETCODE_REQUEST_POWEROFF_SOON,
                id=None,
                is_reply=False,
                expiration=get_future_time(POWEROFF_REQUEST_TIMEOUT),
            )
            poweroff_response: NetworkingMessage | None = (
                await self.networking_handler.request(poweroff_request)
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

            msg_poweroff_ok_approx_timestamp: str = (
                f"The client (local) is shutting down. Its power supply will be cut <t:{approximate_poweroff_timestamp}:R>."
                f"\nIt will be safe to power on the local bot <t:{safe_poweron_timestamp}:R>."
                "\n-# bringing back the power supply before this time will break the power state"
            )
            await self.responder.respond(msg_poweroff_ok_approx_timestamp)
        else:
            await message.add_line(msg_poweroff_request_no_only_shutdown)
            await self.responder.respond(msg_poweroff_ok_only_shutdown)

        logging.info(f"Powering off due to a poweroff command. ({self.invocation.only_shutdown=})")

        graceful_shutdown_linux()


class CommandCallerPoweroff(CommandCallerBase[CommandInvocationPoweroff]):
    minecraft_manager: MinecraftManager
    networking_handler: NetworkingHandler

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        minecraft_manager: MinecraftManager,
        networking_handler: NetworkingHandler,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.minecraft_manager = minecraft_manager
        self.networking_handler = networking_handler

    def make_invocation(
        self, only_shutdown: bool
    ) -> tuple["CommandCallerPoweroff", CommandInvocationPoweroff]:
        return (self, CommandInvocationPoweroff(only_shutdown=only_shutdown))

    def make_call(
        self, invocation: CommandInvocationPoweroff, responder: IResponder
    ) -> CommandCallPoweroff:
        return CommandCallPoweroff(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            minecraft_manager=self.minecraft_manager,
            networking_handler=self.networking_handler,
        )


def setup_cmd_poweroff(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    minecraft_manager: MinecraftManager,
    networking_handler: NetworkingHandler,
) -> None:
    caller: CommandCallerPoweroff = CommandCallerPoweroff(
        locking_component=locking_component,
        permission_info=permission_info,
        minecraft_manager=minecraft_manager,
        networking_handler=networking_handler,
    )

    params: list[click.Parameter] = [
        click.Option(
            ["-s", "--only_shutdown"],
            is_flag=True,
        )
    ]

    command: click.Command = click.Command(
        name=NAME,
        callback=caller.make_invocation,
        add_help_option=False,
        params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
    )
