import asyncclick as click

from .hardcoded import MINECRAFT_SERVER_VIEW_ELLIPSIS
from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CommandsRegistry,
    CallContextGrand,
)
from .main_convenience import bytes_as_lines, bytes_as_lines_length_limited
from .responder import IResponder
from .permissions import IPermissionInfo
from .ranks import RanksRegistry
from .minecraft import MinecraftInstanceEntry

NAME: str = "serverview"


class CommandCallServerView(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
        "lines",
        "max_line_length",
        "name",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    lines: int
    max_line_length: int | None
    name: str

    def __init__(
        self,
        responder: IResponder,
        call_context_grand: CallContextGrand,
        lines: int,
        max_line_length: int | None,
        name: str,
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

        self.lines = lines
        self.max_line_length = max_line_length
        self.name = name

    async def call(self) -> None:
        if self.call_context_grand.minecraft_manager is None:
            await self.responder.respond("There is no minecraft manager.")
            return
        entry: MinecraftInstanceEntry | None = (
            self.call_context_grand.minecraft_manager.get_entry(self.name)
        )
        if entry is None:
            await self.responder.respond(f"No such minecraft entry. {self.name}")
            return
        entry_name: str = entry.name

        await self.responder.respond(f"Selected '{entry_name}'")

        # The buffer is cleared only when starting a new instance
        stdout: bytes = bytes(entry.get_stdout_buffer())

        view_content: str
        if self.max_line_length is None:
            view_content: str = "\n".join(
                bytes_as_lines(
                    stdout,
                    max_lines=self.lines,
                )
            )
        else:
            # The view includes the newline that's always present in mc consoles
            real_max_line_length: int = self.max_line_length + 1
            view_content: str = "\n".join(
                bytes_as_lines_length_limited(
                    stdout,
                    max_lines=self.lines,
                    max_line_length=real_max_line_length,
                    ellipsis=MINECRAFT_SERVER_VIEW_ELLIPSIS,
                )
            )
        msg_t: str = "```\n" + view_content + "\n```"

        await self.responder.respond(msg_t)


class CommandInvocationServerView(ICommandInvocationStandard):
    __slots__ = (
        "lines",
        "max_line_length",
        "name",
    )

    lines: int
    max_line_length: int | None
    name: str

    def __init__(self, lines: int, max_line_length: int | None, name: str) -> None:
        self.lines = lines
        self.max_line_length = max_line_length
        self.name = name

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallServerView:
        return CommandCallServerView(
            responder=responder,
            call_context_grand=call_context_grand,
            lines=self.lines,
            max_line_length=self.max_line_length,
            name=self.name,
        )

    def get_default_respect_locks(self) -> bool:
        return False


def invoke_serverview(
    lines: int, max_line_length: int | None, name: str
) -> CommandInvocationServerView:
    return CommandInvocationServerView(
        lines=lines, max_line_length=max_line_length, name=name
    )


def setup_cmd_serverview(
    commands_registry: CommandsRegistry,
    ranks_registry: RanksRegistry,
    default_target: str,
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_trusted_permission_info()

    params: list[click.Parameter] = [
        click.Argument(["lines"], type=int, required=True),
        click.Argument(["max_line_length"], type=int, required=False, default=None),
        click.Option(
            ["-n", "--name"], type=str, required=False, default=default_target
        ),
    ]
    command: click.Command = click.Command(
        name=NAME, callback=invoke_serverview, add_help_option=False, params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
