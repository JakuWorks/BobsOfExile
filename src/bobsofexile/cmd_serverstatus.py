from dataclasses import dataclass
from collections.abc import Sequence

import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ILockingComponent,
    CommandsRegistry,
    CommandCallBase,
    CommandCallerBase,
)
from .responder import IResponder
from .permission_info import IPermissionInfo

from .minecraft import MinecraftInstanceEntry, MinecraftManager

NAME: str = "serverstatus"


def format_entry_info_for_status(
    name: str,
    entry_running: bool,
    instance_startup_phase: int | None,
    entry_stopping: int | None,
    estimate_max_ram_usage_bytes: int,
) -> str:
    indent: str = "    "
    bytes_in_gb: int = 1024**3
    estimate_max_ram_usage_bytes_gb: float = estimate_max_ram_usage_bytes / bytes_in_gb

    formatted: str = f"{name}:"
    formatted += f"\n{indent}Running: {entry_running}"
    formatted += f"\n{indent}Instance startup phase: {instance_startup_phase}"
    formatted += f"\n{indent}Entry stopping: {entry_stopping}"
    formatted += f"\n{indent}Estimate max RAM usage while running: {estimate_max_ram_usage_bytes_gb}Gb"

    return formatted


@dataclass(frozen=True, slots=True)
class CommandInvocationServerStatus:
    pass


class CommandCallServerStatus(CommandCallBase[CommandInvocationServerStatus]):
    minecraft_manager: MinecraftManager

    def __init__(
        self,
        invocation: CommandInvocationServerStatus,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        minecraft_manager: MinecraftManager,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.minecraft_manager = minecraft_manager

    async def call(self) -> None:
        entries: Sequence[MinecraftInstanceEntry] = (
            self.minecraft_manager.get_all_entries()
        )
        if len(entries) == 0:
            await self.responder.respond("There are no instance entries")
            return

        blocks: list[str] = []
        for entry in entries:
            entry_running: bool = entry.get_running().get()
            instance_startup_phase: int | None
            entry_stopping: bool | None
            if entry_running:
                instance_startup_phase = entry.get_instance_startup_phase().get()
                entry_stopping = entry.get_instance_stopping().get()
            else:
                instance_startup_phase = None
                entry_stopping = None

            formatted: str = format_entry_info_for_status(
                name=entry.name,
                entry_running=entry_running,
                instance_startup_phase=instance_startup_phase,
                entry_stopping=entry_stopping,
                estimate_max_ram_usage_bytes=entry.estimated_max_ram_usage_bytes,
            )
            blocks.append(formatted)

        max_ram_bytes: int = self.minecraft_manager.get_ram_counter().get_max_bytes()
        bytes_in_gb: int = 1024**3
        max_ram_bytes_gb: float = max_ram_bytes / bytes_in_gb
        blocks.append(f"Max ram for all instances: {max_ram_bytes_gb}Gb")

        blocks_joined: str = "\n".join(blocks)
        blocks_formatted: str = f"```\n{blocks_joined}\n```"
        await self.responder.respond(blocks_formatted)


class CommandCallerServerStatus(CommandCallerBase[CommandInvocationServerStatus]):
    minecraft_manager: MinecraftManager

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        minecraft_manager: MinecraftManager,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.minecraft_manager = minecraft_manager

    def make_invocation(
        self,
    ) -> tuple["CommandCallerServerStatus", CommandInvocationServerStatus]:
        return (self, CommandInvocationServerStatus())

    def make_call(
        self, invocation: CommandInvocationServerStatus, responder: IResponder
    ) -> CommandCallServerStatus:
        return CommandCallServerStatus(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            minecraft_manager=self.minecraft_manager,
        )


def setup_cmd_serverstatus(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    minecraft_manager: MinecraftManager,
) -> None:
    caller: CommandCallerServerStatus = CommandCallerServerStatus(
        locking_component=locking_component,
        permission_info=permission_info,
        minecraft_manager=minecraft_manager,
    )

    command: click.Command = click.Command(
        name=NAME,
        callback=caller.make_invocation,
        add_help_option=False,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
    )
