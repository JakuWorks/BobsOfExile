import logging
from typing import Callable, Any, Coroutine

import asyncclick as click
import discord

from .commands import CommandsRegistry, CallContextYoung


class Bot:
    __slots__ = ("prefix", "prefix_l", "client", "registry", "status")

    prefix: str
    prefix_l: int
    client: discord.Client
    registry: CommandsRegistry
    status: str

    def __init__(self, prefix: str, registry: CommandsRegistry, status: str) -> None:
        self.prefix = prefix
        self.prefix_l = len(prefix)
        self.client: discord.Client = discord.Client(intents=self.get_needed_intents())
        self.registry = registry
        self.status = status

        self.client.event(wrap_on_ready(self))
        self.client.event(wrap_on_message(self))
        self.client.event(wrap_on_error())

    async def run(self, token: str) -> None:
        await self.client.start(token)

    def get_needed_intents(self) -> discord.Intents:
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        return intents

    def check_is_prefixed(self, text: str) -> bool:
        return text[: self.prefix_l] == self.prefix

    def get_after_prefix(self, text: str) -> str:
        return text[self.prefix_l :]


def wrap_on_message(bot: Bot) -> Callable[[discord.Message], Coroutine[Any, Any, None]]:
    async def on_message(message_context: discord.Message) -> None:
        if not bot.check_is_prefixed(message_context.content):
            return
        command_text: str = bot.get_after_prefix(message_context.content)
        if command_text == "":
            return
        try:
            call_context: CallContextYoung = CallContextYoung(
                message_context=message_context, respect_command_lock=True
            )
            await bot.registry.call_command(
                command_text, call_context_young=call_context
            )
        except click.UsageError as e:
            if e.ctx is None:
                await message_context.channel.send("Malformed command")
                return
            msg_t: str = "Malformed command.\n" + e.ctx.get_help()
            await message_context.channel.send(msg_t)
        except click.ClickException as e:
            await message_context.channel.send("Unknown click exception")
            logging.error(e)

    return on_message


def wrap_on_ready(bot: Bot) -> Callable[[], Coroutine[Any, Any, None]]:
    logging.info("Bot ready")

    async def on_ready() -> None:
        logging.info("Setting activity")

        # Shit code warning
        status: str
        if bot.status == "":
            status = " "
        else:
            status = bot.status

        activity: discord.CustomActivity = discord.CustomActivity(name=status)
        await bot.client.change_presence(activity=activity)

    return on_ready


def wrap_on_error() -> Callable[[str], Coroutine[Any, Any, None]]:
    async def on_error(event_name: str, *args: Any, **kwargs: Any) -> None:
        try:
            raise
        except Exception as e:
            logging.error("Got error!", exc_info=e)
            raise

    return on_error
