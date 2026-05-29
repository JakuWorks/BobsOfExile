from dataclasses import dataclass

import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ILockingComponent,
    CommandsRegistry,
    CommandCallBase,
    CommandCallerBase,
)
from .responder import IResponder
from .permission_info import IPermissionInfo

from .hardcoded import MINECRAFT_SERVER_VIEW_ELLIPSIS
from .main_convenience import bytes_as_lines, bytes_as_lines_length_limited
from .minecraft import MinecraftInstanceEntry, MinecraftManager

NAME: str = "serverview"


@dataclass(frozen=True, slots=True)
class CommandInvocationServerView:
    lines: int
    max_line_length: int | None
    name: str


class CommandCallServerView(CommandCallBase[CommandInvocationServerView]):
    minecraft_manager: MinecraftManager

    def __init__(
        self,
        invocation: CommandInvocationServerView,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        minecraft_manager: MinecraftManager,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.minecraft_manager = minecraft_manager

    async def call(self) -> None:
        entry: MinecraftInstanceEntry | None = self.minecraft_manager.get_entry(
            self.invocation.name
        )
        if entry is None:
            await self.responder.respond(
                f"No such minecraft entry. {self.invocation.name}"
            )
            return
        entry_name: str = entry.name

        await self.responder.respond(f"Selected '{entry_name}'")

        # The buffer is cleared only when starting a new instance
        stdout: bytes = bytes(entry.get_stdout_buffer())

        view_content: str
        if self.invocation.max_line_length is None:
            view_content: str = "\n".join(
                bytes_as_lines(
                    stdout,
                    max_lines=self.invocation.lines,
                )
            )
        else:
            # The view includes the newline that's always present in mc consoles
            real_max_line_length: int = self.invocation.max_line_length + 1
            view_content: str = "\n".join(
                bytes_as_lines_length_limited(
                    stdout,
                    max_lines=self.invocation.lines,
                    max_line_length=real_max_line_length,
                    ellipsis=MINECRAFT_SERVER_VIEW_ELLIPSIS,
                )
            )
        msg_t: str = "```\n" + view_content + "\n```"

        await self.responder.respond(msg_t)


class CommandCallerServerView(CommandCallerBase[CommandInvocationServerView]):
    minecraft_manager: MinecraftManager

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        minecraft_manager: MinecraftManager,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.minecraft_manager = minecraft_manager

    def make_invocation(
        self, lines: int, max_line_length: int | None, name: str
    ) -> tuple["CommandCallerServerView", CommandInvocationServerView]:
        return (
            self,
            CommandInvocationServerView(
                lines=lines, max_line_length=max_line_length, name=name
            ),
        )

    def make_call(
        self, invocation: CommandInvocationServerView, responder: IResponder
    ) -> CommandCallServerView:
        return CommandCallServerView(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            minecraft_manager=self.minecraft_manager,
        )


def setup_cmd_serverview(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    default_target: str,
    minecraft_manager: MinecraftManager,
) -> None:
    caller: CommandCallerServerView = CommandCallerServerView(
        locking_component=locking_component,
        permission_info=permission_info,
        minecraft_manager=minecraft_manager,
    )

    params: list[click.Parameter] = [
        click.Argument(["lines"], type=int, required=True),
        click.Argument(["max_line_length"], type=int, required=False, default=None),
        click.Option(
            ["-n", "--name"], type=str, required=False, default=default_target
        ),
    ]
    command: click.Command = click.Command(
        name=NAME,
        callback=caller.make_invocation,
        add_help_option=False,
        params=params,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
    )
