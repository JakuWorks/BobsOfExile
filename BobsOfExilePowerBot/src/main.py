"""
Requirements:
discord
tinytuya

Dev Requirements:
mypy
black
"""


import asyncio
import sys
from discord.ext import commands
from OTHER_SETTINGS import LOGS_SEPARATOR as s
from logs import ldbg, linfo
from cfg import Cfg, get_shared_cfg, CfgMasterOptions
from bot import setup_bot, bot_connect, bot_login


async def main() -> None:
    cfg: Cfg = get_shared_cfg()
    token: str = cfg.get_master_str_data(CfgMasterOptions.DISCORD_TOKEN.value, True)
    bot: commands.Bot = setup_bot()
    ldbg("Finished Bot Object Creation")
    linfo(f"All bot commands objects:{s}{str(bot.all_commands)}")

    await bot_login(bot, token)
    await bot_connect(bot)

    ldbg("Bot disconnected! Closing Program!")
    await bot.close()
    raise sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
