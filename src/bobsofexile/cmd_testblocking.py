import logging
import asyncio
import random

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

NAME: str = "testblocking"


class CommandCallTestBlocking(ICommandCall):
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
        t: int = 5
        random_id: int = random.randint(1, 99)
        await self.responder.respond(f"Blocking {t=} ({random_id})")
        logging.info(f"Blocking {t=} ({random_id})")
        await asyncio.sleep(t)
        await self.responder.respond(f"Finished blocking ({random_id})")
        logging.info(f"Finished blocking ({random_id})")


class CommandInvocationTestBlocking(ICommandInvocationStandard):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallTestBlocking:
        return CommandCallTestBlocking(
            responder=responder, call_context_grand=call_context_grand
        )

    def get_default_respect_locks(self) -> bool:
        return True


def invoke_testblocking() -> CommandInvocationTestBlocking:
    return CommandInvocationTestBlocking()


def setup_cmd_testblocking(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    command: click.Command = click.Command(
        name=NAME, callback=invoke_testblocking, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
