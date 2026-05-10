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

NAME: str = "testarg"


class CommandCallTestArg(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
        "testingargument",
        "testingoption",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    testingargument: str
    testingoption: str

    def __init__(
        self,
        responder: IResponder,
        call_context_grand: CallContextGrand,
        testingargument: str,
        testingoption: str,
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

        self.testingargument = testingargument
        self.testingoption = testingoption

    async def call(self) -> None:
        msg: str = f"Testing argument: {self.testingargument}\nTesting option: {self.testingoption}" # fmt: skip
        await self.responder.respond(msg) # fmt: skip
        logging.info(msg)


class CommandInvocationTestArg(ICommandInvocationStandard):
    __slots__ = (
        "testingargument",
        "testingoption",
    )

    testingargument: str
    testingoption: str

    def __init__(self, testingargument: str, testingoption: str) -> None:
        self.testingargument = testingargument
        self.testingoption = testingoption

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallTestArg:
        return CommandCallTestArg(
            responder=responder,
            call_context_grand=call_context_grand,
            testingargument=self.testingargument,
            testingoption=self.testingoption,
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_testarg(
    testingargument: str, testingoption: str
) -> CommandInvocationTestArg:
    return CommandInvocationTestArg(
        testingargument=testingargument, testingoption=testingoption
    )


def setup_cmd_testarg(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_everyone_permission_info()

    params: list[click.Parameter] = [
        click.Argument(["testingargument"], type=str, required=True),
        click.Option(
            ["-to", "--testingoption"],
            type=str,
            required=False,
            default="Default testingoption value",
        ),
    ]
    command: click.Command = click.Command(
        name=NAME, callback=invoke_testarg, add_help_option=False, params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
