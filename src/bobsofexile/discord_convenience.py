import io
import discord

from .hardcoded import BOT_FILE_SEND_THRESHOLD, BOT_FILE_SEND_FILENAME
from .commands import CallContext


async def channel_send_text_or_file(
    content: str,
    channel: "discord.abc.MessageableChannel",  # Pypy 3.11.15 has issues with this type for some reason
    threshold: int = BOT_FILE_SEND_THRESHOLD,
    filename: str = BOT_FILE_SEND_FILENAME,
) -> discord.Message:
    if len(content) > threshold:
        return await channel.send(file=text_to_file(content, filename=filename))
    return await channel.send(content=content)


async def respond_text_or_file_from_call_context(
    context: CallContext, content: str
) -> discord.Message:
    return await channel_send_text_or_file(
        content=content, channel=context.young.message_context.channel
    )


def text_to_file(content: str, filename: str) -> discord.File:
    return discord.File(io.BytesIO(content.encode(encoding="utf-8")), filename=filename)
