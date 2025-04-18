import discord
from discord.ext import commands
from logs import ldbg


def get_correct_intents() -> discord.Intents:
    # Convenience function
    intents: discord.Intents = discord.Intents.default()
    intents.message_content = True
    return intents


async def start_bot(bot: commands.Bot, token: str) -> None:
    ldbg("Logging in")
    await bot.login(token)
    ldbg("Connecting")
    await bot.connect()
    ldbg("Closing")
    await bot.close()

