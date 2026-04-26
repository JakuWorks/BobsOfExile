import pathlib
import logging

import asyncclick as click

from .hardcoded import (
    ENV_KEY_MINECRAFT_SERVER_EXECUTABLE,
    ENV_KEY_MINECRAFT_SERVER_STDOUT_BUFFER_SIZE_BYTES,
    ENV_KEY_MINECRAFT_EMPTY_CHECK_INTERVAL_S,
    ENV_KEY_MINECRAFT_EMPTY_PROLONGED_MINIMUM_SPREE,
    ENV_KEY_MINECRAFT_HOST,
    ENV_KEY_MINECRAFT_PORT,
)

from .main_convenience import (
    EnvironmentVariableError,
    get_env_or_error_path_existing,
    get_env_or_error_int_positive,
    get_env_or_error,
)
from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .minecraft import ServerExecutableMissingError, MinecraftInstance
from .discord_convenience import respond_text_or_file_from_call_context as respond

from .cmd_poweroff import call_cmd_poweroff_raw

NAME: str = "serverstart"


def setup_cmd_serverstart(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_serverstart)
    params: list[click.Parameter] = []
    command: click.Command = click.Command(
        name=NAME, callback=callback, params=params, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_serverstart_raw(call_context: CallContext) -> None:
    try:
        exec_path: pathlib.Path = get_env_or_error_path_existing(
            ENV_KEY_MINECRAFT_SERVER_EXECUTABLE
        )
        max_buffer_bytes: int = get_env_or_error_int_positive(
            ENV_KEY_MINECRAFT_SERVER_STDOUT_BUFFER_SIZE_BYTES
        )
        empty_check_interval_s: int = get_env_or_error_int_positive(
            ENV_KEY_MINECRAFT_EMPTY_CHECK_INTERVAL_S
        )
        empty_prolonged_minimum_spree: int = get_env_or_error_int_positive(
            ENV_KEY_MINECRAFT_EMPTY_PROLONGED_MINIMUM_SPREE
        )
        server_host: str = get_env_or_error(ENV_KEY_MINECRAFT_HOST)
        server_port: int = get_env_or_error_int_positive(ENV_KEY_MINECRAFT_PORT)
    except EnvironmentVariableError as e:
        await respond(call_context, str(e))
        return

    async def on_exit() -> None:
        call_context.grand.server_instance = None
        await respond(call_context, "Server exit.")

    async def on_empty() -> None:
        await respond(call_context, "Server is empty")

    async def on_empty_prolonged() -> None:
        await respond(call_context, "Powering off due to inactivity.")
        # call_context.young.respect_command_lock = False # Unnecessary because raw bypasses lock anyway
        await call_cmd_poweroff_raw(call_context=call_context)
        # call_context.young.respect_command_lock = True

    msg_starting_server: str = (
        "Starting server... You can `poweroff` the OS later after you're done playing."
        "\n-# Powering off is optional because there's an automatic system for it in-place"
    )
    await respond(call_context, msg_starting_server)

    try:
        call_context.grand.server_instance = MinecraftInstance(
            start_executable=pathlib.Path(exec_path),
            stdout_max_bytes=max_buffer_bytes,
            on_exit_async=on_exit,
            on_empty_async=on_empty,
            on_empty_prolonged_async=on_empty_prolonged,
            empty_check_interval_s=empty_check_interval_s,
            empty_prolonged_minimum_spree=empty_prolonged_minimum_spree,
            server_host=server_host,
            server_port=server_port,
        )
    except ServerExecutableMissingError:
        await respond(call_context, "The server executable is missing")
        await on_exit()
        return
    except Exception as e:
        logging.error(e)
        await respond(call_context, "An unknown error was raised and has been logged")
        await on_exit()
        return

    try:
        await call_context.grand.server_instance.start()
    except Exception as e:
        logging.error(e)
        await respond(call_context, "An unknown error was raised and has been logged")
        await on_exit()
        return


async def call_cmd_serverstart(ctx: click.Context, /) -> None: ...


call_cmd_serverstart = simple_wrap_command_call(
    call_cmd_serverstart_raw, respect_lock=True
)
