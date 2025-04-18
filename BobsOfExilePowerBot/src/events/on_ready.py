import asyncio
from discord.ext import commands
from logs import levent, ldbg
from bot_activity import setup_auto_host_power_activity_update, update_host_power_activity


async def on_ready(bot: commands.Bot) -> None:
    levent("Ready")
    ldbg(f"{bot.user} is Online")

    await update_host_power_activity(bot)
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    await setup_auto_host_power_activity_update(bot, loop)