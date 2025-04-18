from typing import Any
import asyncio
import discord
from discord.ext import commands
from common import TuyaResponse, Stringable
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
    CMD_HOST_PRINT_POWER_CODE,
    HOST_POWER_STATUS_ACTIVITY_UPDATE_DELAY_SECONDS,
)
from logs import ldbg, lwarn
from cfg import Cfg, get_shared_cfg
from tuya_helpers import get_response_ok
from host_status_helpers import (
    get_parsed_status_from_response,
    get_host_status_from_cfg,
)
from NonStockpilingScheduleTask import NonStockpilingScheduleTask


async def set_bot_activity(bot: commands.Bot, msg: str) -> None:
    logs_prefix: str = f"Msg: {msg}{s}"
    ldbg(f"{logs_prefix}Setting Bot Activity")
    activity: discord.Activity = discord.Activity(
        type=discord.ActivityType.watching, name=msg
    )
    await bot.ws.change_presence(activity=activity)


async def update_host_power_activity(bot: commands.Bot) -> None:
    ldbg("Updating activity with host power status")
    cfg: Cfg = get_shared_cfg()
    status_response: TuyaResponse = get_host_status_from_cfg(cfg)
    ok: bool = get_response_ok(status_response)
    if not ok:
        return
    parsed: dict[str, Any] = get_parsed_status_from_response(status_response)
    code: str = CMD_HOST_PRINT_POWER_CODE
    if not code in parsed:
        lwarn(f"Failed to get power status (given code ({code}) not found in response)")
        await set_bot_activity(bot, "Failed to get status")
        return
    power_raw: Stringable = parsed[code]
    msg: str = get_host_power_status_msg(power_raw)
    await set_bot_activity(bot, msg)


def get_host_power_status_msg(power_raw: Stringable) -> str:
    power_state: str
    try:
        power_b: bool = bool(power_raw)
        power_state = "ON" if power_b else "OFF"
    except:
        power_state = str(power_raw)
    msg: str = f"Power: {power_state}"
    return msg


async def set_bot_activity_from_power_status(
    bot: commands.Bot, status: Stringable
) -> None:
    msg: str
    if isinstance(status, str):
        msg = status
    else:
        msg = get_host_power_status_msg(status)
    await set_bot_activity(bot, msg)


async def setup_auto_host_power_activity_update(
    bot: commands.Bot, loop: asyncio.AbstractEventLoop
) -> None:
    ldbg("Setting up periodic automatic bot host power state activity updating")

    async def job() -> None:
        await update_host_power_activity(bot)

    every_secs: int = HOST_POWER_STATUS_ACTIVITY_UPDATE_DELAY_SECONDS
    NonStockpilingScheduleTask(job, loop, every_secs)
