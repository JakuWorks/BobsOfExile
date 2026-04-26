import asyncclick as click

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond
from .networking import NetworkingMessage
from .hardcoded import TESTPING_TIMEOUT, NETCODE_REQUEST_PING
from .main_convenience import get_future_time

NAME: str = "testping"


def setup_cmd_testping(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_testping)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_testping_raw(call_context: CallContext) -> None:
    request_ping_msg: NetworkingMessage = NetworkingMessage(code=NETCODE_REQUEST_PING, is_reply=False, expiration=get_future_time(after_seconds=TESTPING_TIMEOUT), id=None)
    response: NetworkingMessage | None = await call_context.grand.networking_handler.request(request_ping_msg, timeout=TESTPING_TIMEOUT)
    if response:
        await respond(call_context, "Pong!")
    else:
        await respond(call_context, "Timed out.")


async def call_cmd_testping(ctx: click.Context, /) -> None: ...


call_cmd_testping = simple_wrap_command_call(
    call_cmd_testping_raw, respect_lock=True
)
