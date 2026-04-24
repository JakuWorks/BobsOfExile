import asyncclick as click

from .hardcoded import MINECRAFT_SERVER_VIEW_ELLIPSIS

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond

NAME: str = "serverview"


def setup_cmd_serverview(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_trusted_permission_info()

    callback = click.pass_context(call_cmd_serverview)
    params: list[click.Parameter] = [
        click.Argument(["lines"], type=int, required=True),
        click.Argument(["max_line_length"], type=int, required=False, default=None),
    ]
    command: click.Command = click.Command(
        name=NAME, callback=callback, params=params, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_serverview_raw(
    call_context: CallContext, lines: int, max_line_length: int | None
) -> None:
    if call_context.grand.server_instance is None:
        await respond(call_context, "Server was never started")
        return

    if not call_context.grand.server_instance.running:
        await respond(call_context, "Server is not running")

    view_content: str
    if max_line_length is None:
        view_content: str = "\n".join(
            call_context.grand.server_instance.stdout_buffer.as_lines(
                max_lines=lines,
            )
        )
    else:
        max_line_length += (
            1  # The view includes the newline that's always present in mc consoles
        )
        view_content: str = "\n".join(
            call_context.grand.server_instance.stdout_buffer.as_lines_length_limited(
                max_lines=lines,
                max_line_length=max_line_length,
                ellipsis=MINECRAFT_SERVER_VIEW_ELLIPSIS,
            )
        )
    msg_t: str = "```\n" + view_content + "\n```"

    await respond(call_context, msg_t)


async def call_cmd_serverview(
    ctx: click.Context, /, lines: int, max_line_length: int | None
) -> None: ...


call_cmd_serverview = simple_wrap_command_call(call_cmd_serverview_raw, respect_lock=False)
