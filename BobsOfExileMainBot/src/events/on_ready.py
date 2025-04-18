from discord.ext import commands
from logs import levent, ldbg
from OTHER_SETTINGS import LOGS_SEPARATOR as s


async def on_ready(bot: commands.Bot) -> None:
    levent("Ready")
    logs_infix: str = f"{bot.user=}{s}"
    ldbg(f"{logs_infix}Online!")
