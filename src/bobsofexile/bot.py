import logging
from typing import Callable, Any, Coroutine

import asyncclick as click
import discord

from .discord_responder import DiscordResponder
from .commands import CommandsRegistry, CommandsRegistryEntryNotFoundError
from .responder import IResponder
from .async_convenience import IBooleanEvent, IMutableBooleanEvent, BooleanEvent


class Bot:
    __slots__ = (
        "prefix",
        "prefix_l",
        "client",
        "registry",
        "status",
        "_on_ready_event",
    )

    prefix: str
    prefix_l: int
    client: discord.Client
    registry: CommandsRegistry
    status: str
    _on_ready_event: IMutableBooleanEvent

    def __init__(self, prefix: str, registry: CommandsRegistry, status: str) -> None:
        self.prefix = prefix
        self.prefix_l = len(prefix)
        self.client: discord.Client = discord.Client(intents=self.get_needed_intents())
        self.registry = registry
        self.status = status
        self._on_ready_event = BooleanEvent(
            "Bot was set as ready", "Bot was set as ready AGAIN"
        )

    def setup_events(self) -> None:
        self.client.event(self._wrap_on_ready(on_ready_event=self._on_ready_event))
        self.client.event(self._wrap_on_message())
        self.client.event(self._wrap_on_error())

    async def login(self, token: str) -> None:
        await self.client.login(token)

    async def connect(self) -> None:
        await self.client.connect(reconnect=True)

    def get_ready_event(self) -> IBooleanEvent:
        return self._on_ready_event

    def get_needed_intents(self) -> discord.Intents:
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        return intents

    def check_is_prefixed(self, text: str) -> bool:
        return text[: self.prefix_l] == self.prefix

    def get_after_prefix(self, text: str) -> str:
        return text[self.prefix_l :]

    def _wrap_on_message(
        self,
    ) -> Callable[[discord.Message], Coroutine[Any, Any, None]]:
        async def on_message(message_context: discord.Message) -> None:
            if not self.check_is_prefixed(message_context.content):
                return
            command_text: str = self.get_after_prefix(message_context.content)
            if command_text == "":
                return

            responder: IResponder = DiscordResponder(
                sending_channel=message_context.channel
            )

            try:
                await self.registry.call_command(
                    command_text,
                    author_id=str(message_context.author.id),
                    responder=responder,
                )
            except CommandsRegistryEntryNotFoundError:
                pass
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

    def _wrap_on_ready(
        self, on_ready_event: IMutableBooleanEvent
    ) -> Callable[[], Coroutine[Any, Any, None]]:
        logging.info("Bot ready")

        async def on_ready() -> None:
            logging.info("Setting activity")

            # Shit code warning
            status: str
            if self.status == "":
                status = " "
            else:
                status = self.status

            activity: discord.CustomActivity = discord.CustomActivity(name=status)
            await self.client.change_presence(activity=activity)
            on_ready_event.set()

        return on_ready

    def _wrap_on_error(self) -> Callable[[str], Coroutine[Any, Any, None]]:
        async def on_error(event_name: str, *args: Any, **kwargs: Any) -> None:
            try:
                raise
            except Exception as e:
                logging.error("Got error!", exc_info=e)
                raise

        return on_error
