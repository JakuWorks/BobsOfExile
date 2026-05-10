import io
import discord
import discord.abc

from .hardcoded import BOT_FILE_SEND_CHARS_THRESHOLD, BOT_FILE_SEND_FILENAME


async def channel_send_text_or_file(
    content: str,
    channel: discord.abc.Messageable,
    threshold: int = BOT_FILE_SEND_CHARS_THRESHOLD,
    filename: str = BOT_FILE_SEND_FILENAME,
) -> discord.Message:
    if len(content) > threshold:
        return await channel.send(file=text_to_file(content, filename=filename))
    return await channel.send(content=content)


def text_to_file(content: str, filename: str) -> discord.File:
    return discord.File(io.BytesIO(content.encode(encoding="utf-8")), filename=filename)
