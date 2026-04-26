import asyncclick as click

from .hardcoded import (
    NETCODE_REQUEST_POWER_DEVICE_STATUS,
    NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
    NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
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
from .main_convenience import get_future_time

NAME: str = "testpowerdeviceconnectionrequest"


def setup_cmd_testpowerdeviceconnectionrequest(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_testpowerdeviceconnectionrequest)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_testpowerdeviceconnectionrequest_raw(
    call_context: CallContext,
) -> None:
    await respond(call_context, "Trying")
    msg_request: NetworkingMessage = NetworkingMessage(
        code=NETCODE_REQUEST_POWER_DEVICE_STATUS, id=None, is_reply=False, expiration=get_future_time(POWER_DEVICE_STATUS_REQUEST_TIMEOUT)
    )
    reply: NetworkingMessage | None = (
        await call_context.grand.networking_handler.request(
            msg=msg_request, timeout=POWER_DEVICE_STATUS_REQUEST_TIMEOUT
        )
    )
    if reply is None:
        await respond(call_context, "Timed out")
        return
    if reply.code == NETCODE_REPLY_POWER_DEVICE_STATUS_OK:
        await respond(call_context, f"Got: OK ({reply.code})")
        return
    if reply.code == NETCODE_REPLY_POWER_DEVICE_STATUS_NO:
        await respond(call_context, f"Got: NO ({reply.code})")
        return
    await respond(call_context, f"Got unknown code ({reply.code})")


async def call_cmd_testpowerdeviceconnectionrequest(ctx: click.Context, /) -> None: ...


call_cmd_testpowerdeviceconnectionrequest = simple_wrap_command_call(
    call_cmd_testpowerdeviceconnectionrequest_raw, respect_lock=False
)
