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

NAME: str = "testpermissions"


class CommandCallTestPermissions(ICommandCall):
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
        await self.responder.respond("Command success")
        logging.info("permission test")


class CommandInvocationTestPermissions(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallTestPermissions:
        return CommandCallTestPermissions(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_testpermissions() -> CommandInvocationTestPermissions:
    return CommandInvocationTestPermissions()


def setup_cmd_testpermissions(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_no_one_permission_info()

    command: click.Command = click.Command(
        name=NAME, callback=invoke_testpermissions, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
