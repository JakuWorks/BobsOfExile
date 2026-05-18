import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CommandsRegistry,
    CallContextGrand,
)
from .responder import IResponder
from .permissions import IPermissionInfo
from .minecraft import MinecraftInstanceEntry
from .ranks import RanksRegistry

NAME: str = "servercmd"


class CommandCallServerCmd(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
        "cmd",
        "name",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    cmd: str
    name: str

    def __init__(
        self,
        responder: IResponder,
        call_context_grand: CallContextGrand,
        cmd: str,
        name: str,
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

        self.cmd = cmd
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
            await self.responder.respond(f"Instance is not running. ({entry_name})")
            return
        if entry.get_instance_stopping().get():
            await self.responder.respond(f"Instance is stopping. ({entry_name})")
            return
        startup_phase: int = entry.get_instance_startup_phase().get()
        if startup_phase < 2:
            await self.responder.respond(f"Instance isn't ready yet. (startup phase: {startup_phase}, but must be 2). ({entry_name})") # fmt: skip
            return

        try:
            await entry.send_command(self.cmd)
        except Exception as e:
            await self.responder.respond(
                f"Got error ({entry_name})!\n```\n{repr(e)}\n```"
            )
        else:
            await self.responder.respond(f"Sent command. ({entry_name})")


class CommandInvocationServerCmd(ICommandInvocationStandard):
    __slots__ = (
        "cmd",
        "name",
    )

    cmd: str
    name: str

    def __init__(self, cmd: str, name: str) -> None:
        self.cmd = cmd
        self.name = name

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallServerCmd:
        return CommandCallServerCmd(
            responder=responder,
            call_context_grand=call_context_grand,
            cmd=self.cmd,
            name=self.name,
        )

    def get_default_respect_locks(self) -> bool:
        return True


def invoke_servercmd(cmd: str, name: str) -> CommandInvocationServerCmd:
    return CommandInvocationServerCmd(cmd=cmd, name=name)


def setup_cmd_servercmd(
    commands_registry: CommandsRegistry,
    ranks_registry: RanksRegistry,
    default_target: str,
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_trusted_permission_info()

    params: list[click.Parameter] = [
        click.Argument(["cmd"], type=str, required=True),
        click.Option(
            ["-n", "--name"], type=str, required=False, default=default_target
        ),
    ]
    command: click.Command = click.Command(
        name=NAME, callback=invoke_servercmd, add_help_option=False, params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
