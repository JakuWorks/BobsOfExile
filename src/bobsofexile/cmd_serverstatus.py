import asyncclick as click
from collections.abc import Sequence

from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CommandsRegistry,
    CallContextGrand,
)
from .responder import IResponder
from .permissions import IPermissionInfo
from .ranks import RanksRegistry
from .minecraft import MinecraftInstanceEntry

NAME: str = "serverstatus"


class CommandCallServerStatus(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    def __init__(
        self,
        responder: IResponder,
        call_context_grand: CallContextGrand,
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

    async def call(self) -> None:
        if self.call_context_grand.minecraft_manager is None:
            await self.responder.respond("There is no minecraft manager.")
            return
        entries: Sequence[MinecraftInstanceEntry] = (
            self.call_context_grand.minecraft_manager.get_all_entries()
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

        max_ram_bytes: int = (
            self.call_context_grand.minecraft_manager.get_ram_counter().get_max_bytes()
        )
        bytes_in_gb: int = 1024**3
        max_ram_bytes_gb: float = max_ram_bytes / bytes_in_gb
        blocks.append(f"Max ram for all instances: {max_ram_bytes_gb}Gb")

        blocks_joined: str = "\n".join(blocks)
        blocks_formatted: str = f"```\n{blocks_joined}\n```"
        await self.responder.respond(blocks_formatted)


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


class CommandInvocationServerStatus(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallServerStatus:
        return CommandCallServerStatus(
            responder=responder,
            call_context_grand=call_context_grand,
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_serverstatus() -> CommandInvocationServerStatus:
    return CommandInvocationServerStatus()


def setup_cmd_serverstatus(
    commands_registry: CommandsRegistry,
    ranks_registry: RanksRegistry,
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_trusted_permission_info()

    params: list[click.Parameter] = []
    command: click.Command = click.Command(
        name=NAME, callback=invoke_serverstatus, add_help_option=False, params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
