from collections.abc import MutableSequence

import discord


class DiscordStreamingMessage:
    __slots__ = ("lines", "command_context", "message")

    lines: MutableSequence[str]
    command_context: discord.Message
    message: discord.Message | None

    def __init__(self, initial_content: str, command_context: discord.Message) -> None:
        self.command_context = command_context
        self.lines = [initial_content]
        self.message = None

    async def start(self) -> None:
        assert self.message is None, "Streaming message can only be started once"
        self.message = await self.command_context.channel.send(self.lines_formatted())

    async def add_line(self, line: str) -> None:
        assert self.message is not None, "Streaming message was not started"
        self.lines.append(line)
        await self.message.edit(content=self.lines_formatted())

    def lines_formatted(self) -> str:
        return "```\n" + "\n".join(self.lines) + "\n```"
