from .responder import IResponder, ILongResponse
from .discord_convenience import channel_send_text_or_file
from .responder import IResponder
from .main_convenience import get_env_or_error_int_positive
from .hardcoded import ENV_KEY_DEFAULT_RESPONDER_DISCORD_CHANNEL_ID

import discord
import discord.abc


class DiscordLongResponse(ILongResponse):
    __slots__ = (
        "sending_channel",
        "inner_text",
        "started_message",
    )

    sending_channel: discord.abc.Messageable
    inner_text: str
    started_message: discord.Message | None

    def __init__(
        self, sending_channel: discord.abc.Messageable, initial_msg: str | None
    ) -> None:
        self.sending_channel = sending_channel
        self.started_message = None

        if initial_msg is not None:
            self.inner_text = initial_msg
        else:
            self.inner_text = ""

    def inner_text_formatted(self) -> str:
        return "```\n" + self.inner_text + "\n```"

    async def start(self) -> None:
        assert self.started_message is None, "Long message can only be started once"
        self.started_message = await self.sending_channel.send(
            self.inner_text_formatted()
        )

    async def update(self) -> None:
        assert self.started_message is not None, "Long response message be started"
        await self.started_message.edit(content=self.inner_text_formatted())

    async def add_text(self, text: str) -> None:
        self.inner_text += text
        await self.update()

    async def add_line(self, line: str) -> None:
        await self.add_text("\n" + line)


class DiscordResponder(IResponder):
    __slots__ = ("sending_channel",)

    sending_channel: discord.abc.Messageable

    def __init__(self, sending_channel: discord.abc.Messageable) -> None:
        self.sending_channel = sending_channel

    async def respond(self, msg: str) -> None:
        await channel_send_text_or_file(content=msg, channel=self.sending_channel)

    def new_long_response(self, init_msg: str | None) -> ILongResponse:
        return DiscordLongResponse(
            sending_channel=self.sending_channel, initial_msg=init_msg
        )


class DefaultResponderChannelNotExistsError(Exception):
    pass


class DefaultResponderChannelNotMessageableError(Exception):
    pass


def get_default_responder_from_config(client: discord.Client) -> IResponder:
    """Client must be ready if the responder uses a discord channel"""

    # Used so that the default responder can be lazy loaded or not loaded at all if not needed
    channel_id: int = get_env_or_error_int_positive(
        ENV_KEY_DEFAULT_RESPONDER_DISCORD_CHANNEL_ID
    )
    channel: (
        discord.abc.GuildChannel | discord.Thread | discord.abc.PrivateChannel | None
    ) = client.get_channel(channel_id)
    if channel is None:
        raise DefaultResponderChannelNotExistsError(
            f"The channel for the default responder does not exist. (type: {type(channel)}). Please adjust your configuration"
        )
    if not isinstance(channel, discord.abc.Messageable):
        raise DefaultResponderChannelNotMessageableError(
            f"The channel for the default responder is not messageable. (type: {type(channel)}). Please adjust your configuration"
        )
    return DiscordResponder(sending_channel=channel)
