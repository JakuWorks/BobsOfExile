import logging
import asyncio

import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CommandsRegistry,
    CallContextGrand,
)
from .responder import IResponder, ILongResponse
from .permissions import IPermissionInfo
from .ranks import RanksRegistry

NAME: str = "teststream"


class CommandCallTestStream(ICommandCall):
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
        message: ILongResponse = self.responder.new_long_response(
            init_msg="initial content",
        )
        await message.start()
        for i in range(3):
            await message.add_line(f"edit {i}")
            await asyncio.sleep(0.5)
        logging.info("Streamtest")


class CommandInvocationTestStream(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallTestStream:
        return CommandCallTestStream(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_teststream() -> CommandInvocationTestStream:
    return CommandInvocationTestStream()


def setup_cmd_teststream(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    command: click.Command = click.Command(
        name=NAME, callback=invoke_teststream, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
