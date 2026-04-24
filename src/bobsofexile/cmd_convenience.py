import asyncclick as click

from .commands import CommandEntry, CommandsRegistry, CallContextOld
from .permissions import PermissionInfo


def simple_setup_cmd(
    name: str,
    click_command: click.Command,
    commands_registry: CommandsRegistry,
    permission_info: PermissionInfo,
) -> None:
    call_context_old: CallContextOld = CallContextOld(
        permission_resolver=permission_info
    )

    command_entry: CommandEntry = CommandEntry(
        name=name, command=click_command, call_context_old=call_context_old
    )

    commands_registry.add_entry(command_entry)
