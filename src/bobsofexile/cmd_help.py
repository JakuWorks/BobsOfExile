import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CallContextGrand,
    CommandsRegistry,
)
from .responder import IResponder
from .permissions import IPermissionInfo
from .ranks import RanksRegistry

NAME: str = "help"


class CommandCallHelp(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
        "cmd_or_empty",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    cmd_or_empty: str | None

    def __init__(
        self,
        responder: IResponder,
        call_context_grand: CallContextGrand,
        cmd_or_empty: str | None,
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

        self.cmd_or_empty = cmd_or_empty

    async def call(self) -> None:
        if self.call_context_grand.commands_registry is None:
            # This should NEVER happen
            await self.responder.respond("No commands registry")
            return

        if self.cmd_or_empty is not None:
            cmd_help: str | None = (
                self.call_context_grand.commands_registry.get_command_help(
                    command=self.cmd_or_empty
                )
            )
            if cmd_help is None:
                await self.responder.respond("No command found")
            else:
                await self.responder.respond(cmd_help)
        else:
            await self.responder.respond(
                self.call_context_grand.commands_registry.get_all_help()
            )


class CommandInvocationHelp(ICommandInvocationStandard):
    __slots__ = ("cmd_or_empty",)

    cmd_or_empty: str | None

    def __init__(self, cmd_or_empty: str | None) -> None:
        self.cmd_or_empty = cmd_or_empty

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallHelp:
        return CommandCallHelp(
            responder=responder,
            call_context_grand=call_context_grand,
            cmd_or_empty=self.cmd_or_empty,
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_help(cmd_or_empty: str | None) -> CommandInvocationHelp:
    return CommandInvocationHelp(cmd_or_empty=cmd_or_empty)


def setup_cmd_help(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    params: list[click.Parameter] = [
        click.Argument(["cmd_or_empty"], type=str, required=False, default=None)
    ]
    command: click.Command = click.Command(
        name=NAME, callback=invoke_help, add_help_option=False, params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
