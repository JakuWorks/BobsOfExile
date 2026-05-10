import asyncclick as click

from .minecraft import MinecraftInstanceEntry, MinecraftEntryStartPreconfiguration
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

NAME: str = "serverstart"


class CommandCallServerStart(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
        "name",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    name: str

    def __init__(
        self, responder: IResponder, call_context_grand: CallContextGrand, name: str
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand
        self.name = name

    async def call(self) -> None:
        if self.call_context_grand.minecraft_manager is None:
            await self.responder.respond("There is no minecraft manager.")
            return
        entry: MinecraftInstanceEntry | None = (
            self.call_context_grand.minecraft_manager.get_entry(self.name)
        )
        if entry is None:
            await self.responder.respond("No such minecraft entry.")
            return
        if entry.get_running().get():
            await self.responder.respond("Instance is already running.")
            return
        entry_preconfiguration: MinecraftEntryStartPreconfiguration | None = (
            self.call_context_grand.minecraft_manager.get_entry_start_preconfiguration(
                self.name
            )
        )
        if entry_preconfiguration is None:
            await self.responder.respond(
                "There is no start preconfiguration for this entry."
            )
            return

        entry_name: str = entry.name  # has proper case

        msg_starting_server: str = (
            "Starting server... You can `poweroff` the OS later after you're done playing."
            "\n-# Powering off is optional because there's an automatic system for it in-place"
        )

        await self.responder.respond(msg_starting_server)

        async def on_empty() -> None:
            await self.responder.respond("Server is empty")

        async def on_empty_prolonged() -> None:
            await self.responder.respond(f"Stopping instance '{entry_name}' off due to inactivity.") # fmt: skip

        async def on_exit() -> None:
            await self.responder.respond("Server exit.")

        async def on_entry_started() -> None:
            await self.responder.respond("Entry started")

        async def on_instance_stopping() -> None:
            await self.responder.respond("Instance stopping")

        await self.call_context_grand.minecraft_manager.start_entry_with_preconfiguration(
            entry=entry,
            preconfiguration=entry_preconfiguration,
            on_empty_hooks=[on_empty],
            on_empty_prolonged_hooks=[on_empty_prolonged],
            on_entry_finish_hooks=[on_exit],
            on_entry_started_hooks=[on_entry_started],
            on_instance_stopping_hooks=[on_instance_stopping],
        )


class CommandInvocationServerStart(ICommandInvocationStandard):
    __slots__ = ("name",)

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallServerStart:
        return CommandCallServerStart(
            responder=responder, call_context_grand=call_context_grand, name=self.name
        )

    def get_default_respect_locks(self) -> bool:
        return True


def invoke_serverstart(name: str) -> CommandInvocationServerStart:
    return CommandInvocationServerStart(name=name)


def setup_cmd_serverstart(
    commands_registry: CommandsRegistry,
    ranks_registry: RanksRegistry,
    default_target: str,
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    params: list[click.Parameter] = [
        click.Option(["-n", "--name"], type=str, required=False, default=default_target)
    ]
    command: click.Command = click.Command(
        name=NAME, callback=invoke_serverstart, add_help_option=False, params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
