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

NAME: str = "dangerous_instant_poweroff"


def setup_cmd_dangerous_instant_poweroff(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_trusted_permission_info()

    callback = click.pass_context(call_cmd_dangerous_instant_poweroff)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_dangerous_instant_poweroff_raw(call_context: CallContext) -> None:
    if call_context.grand.client_power_controller is None:
        await respond(
            call_context, "Client power controller is missing. Cannot cut power."
        )
        return

    await respond(call_context, "CUTTING POWER.")
    logging.info("CUTTING POWER")

    poweroff_retrier: AsyncIterable[int] = (
        call_context.grand.client_power_controller.power_off_async_with_retries(
            retries=POWEROFF_RETRIES, interval=POWEROFF_RETRY_INTERVAL
        )
    )
    success_final: bool = False
    async for success in poweroff_retrier:
        if success:
            await respond(call_context, "Success")
            success_final = True
            break
        await respond(call_context, "Failure")
    if success_final:
        await respond(call_context, "Final: Success")
    else:
        await respond(call_context, "Final: Failure")


async def call_cmd_dangerous_instant_poweroff(ctx: click.Context, /) -> None: ...


call_cmd_dangerous_instant_poweroff = simple_wrap_command_call(
    call_cmd_dangerous_instant_poweroff_raw, respect_lock=False
)
