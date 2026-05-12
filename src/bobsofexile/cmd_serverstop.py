import asyncclick as click

from .commands import (
    ICommandCall,
    ICommandInvocationStandard,
    CommandsRegistry,
    simple_setup_cmd,
    CallContextGrand,
)
from .responder import IResponder
from .permissions import IPermissionInfo
from .ranks import RanksRegistry
from .minecraft import MinecraftInstanceEntry

NAME: str = "serverstop"


class CommandCallServerStop(ICommandCall):
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
            await self.responder.respond(f"No such minecraft entry. ({self.name})")
            return
        entry_name: str = entry.name
        if not entry.get_running().get():
            await self.responder.respond(f"This server is not running. ({entry_name})")
            return
        if entry.get_instance_stopping().get():
            await self.responder.respond(f"This server is already stopping. ({entry_name})")
            return
        await self.responder.respond(f"The server will stop soon. ({entry_name})")
        entry.stop()


class CommandInvocationServerStop(ICommandInvocationStandard):
    __slots__ = ("name",)

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallServerStop:
        return CommandCallServerStop(
            responder=responder, call_context_grand=call_context_grand, name=self.name
        )

    def get_default_respect_locks(self) -> bool:
        return True


def invoke_serverstop(name: str) -> CommandInvocationServerStop:
    return CommandInvocationServerStop(name=name)


def setup_cmd_serverstop(
    commands_registry: CommandsRegistry,
    ranks_registry: RanksRegistry,
    default_target: str,
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_trusted_permission_info()

    params: list[click.Parameter] = [
        click.Option(
            ["-n", "--name"], type=str, required=False, default=default_target
        ),
    ]
    command: click.Command = click.Command(
        name=NAME, callback=invoke_serverstop, add_help_option=False, params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
