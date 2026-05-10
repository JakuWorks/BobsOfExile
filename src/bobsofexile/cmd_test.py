import logging

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
from .ranks import RanksRegistry

NAME: str = "test"


class CommandCallTest(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    def __init__(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

    async def call(self) -> None:
        await self.responder.respond("Testing hello!")
        logging.info("Test")


class CommandInvocationTest(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallTest:
        return CommandCallTest(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_test() -> CommandInvocationTest:
    return CommandInvocationTest()


def setup_cmd_test(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    command: click.Command = click.Command(
        name=NAME, callback=invoke_test, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
