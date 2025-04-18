from typing import Any
from decimal import Decimal
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
    CMD_HOST_PRINT_STATUS_ACCESS,
    CMD_HOST_PRINT_AT_CODE_ACCESS,
    CMD_HOST_PRINT_WATTAGE_ACCESS,
    CMD_HOST_PRINT_POWER_ACCESS,
    CMD_HOST_PRINT_WATTAGE_CODE,
    CMD_HOST_PRINT_WATTAGE_FACTOR,
    CMD_HOST_PRINT_WATTAGE_DECIMAL_PLACES,
    CMD_HOST_PRINT_POWER_CODE,
)
from common import (
    Stringable,
    TuyaResponse,
    BotContext,
)
from logs import lcmd, ldbg, lwarn
from cfg import Cfg, get_shared_cfg
from bot_access import generic_handle_access
from tuya_helpers import get_response_ok
from host_status_helpers import (
    get_host_status_from_cfg,
    get_parsed_status_from_response,
)
from bot_activity import set_bot_activity_from_power_status


async def handle_status_response_ok(
    ctx: BotContext, status_response: TuyaResponse
) -> bool:
    # -> is_ok
    # This function exists only to reduce boilerplate
    ok: bool = get_response_ok(status_response)
    if not ok:
        await ctx.send(f"Got error!\n```\n{str(status_response)}\n```")
        return False
    return True


async def host_print_status(ctx: BotContext) -> None:
    """Host's power controller status. Alias: host-stats"""
    lcmd("Command triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_HOST_PRINT_STATUS_ACCESS)
    if not authorized:
        return
    cfg: Cfg = get_shared_cfg()
    status_response: TuyaResponse = get_host_status_from_cfg(cfg)
    ok: bool = await handle_status_response_ok(ctx, status_response)
    if not ok:
        return
    await ctx.send(f"Got response\n```\n{str(status_response)}\n```")


async def host_print_at_code(ctx: BotContext, code: str) -> None:
    """Host's specific info Usage & Alias: host-code CODE"""
    # ^ Discord's built in !help command greatly limits the length of these docstrings
    # Assumes all codes don't contain spaces
    lcmd("Command triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_HOST_PRINT_AT_CODE_ACCESS)
    if not authorized:
        return
    logs_infix: str = f"Code: {code}{s}"

    cfg: Cfg = get_shared_cfg()
    status_response: TuyaResponse = get_host_status_from_cfg(cfg)
    ok: bool = await handle_status_response_ok(ctx, status_response)
    if not ok:
        return
    parsed: dict[str, Any] = get_parsed_status_from_response(status_response)

    if not code in parsed:
        ldbg(f"{logs_infix}Couldn't find any value")
        await ctx.send(f"Couldn't find any value at code: `{code}`")
        return
    value: Stringable = parsed[code]  # Assuming it's stringable
    ldbg(f"{logs_infix}Value: {value}{s}Found value")
    await ctx.send(f"Raw Value: `{value}`")

    if code == CMD_HOST_PRINT_POWER_CODE:
        await set_bot_activity_from_power_status(ctx.bot, value)


async def host_print_wattage(ctx: BotContext) -> None:
    """Host's wattage. Alias: host-watts"""
    lcmd("Command triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_HOST_PRINT_WATTAGE_ACCESS)
    if not authorized:
        return

    cfg: Cfg = get_shared_cfg()
    status_response: TuyaResponse = get_host_status_from_cfg(cfg)
    ok: bool = await handle_status_response_ok(ctx, status_response)
    if not ok:
        return
    parsed: dict[str, Any] = get_parsed_status_from_response(status_response)

    wattage_raw: Any = parsed.get(CMD_HOST_PRINT_WATTAGE_CODE)
    ldbg(f"{wattage_raw}{s}Got raw host wattage")
    try:
        wattage_n: Decimal = Decimal(wattage_raw)
        d: int = CMD_HOST_PRINT_WATTAGE_DECIMAL_PLACES
        wattage: Decimal = wattage_n * Decimal(CMD_HOST_PRINT_WATTAGE_FACTOR)
        await ctx.send(f"Current wattage: {wattage:.{d}f}W")
    except:
        lwarn("Failed to get wattage text! Displaying raw value")
        await ctx.send(f"Current __raw__ wattage value: {wattage_raw}")


async def host_print_power(ctx: BotContext) -> None:
    """Host's power (on/off) status. Alias: host-pwr"""
    lcmd("Command triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_HOST_PRINT_POWER_ACCESS)
    if not authorized:
        return

    cfg: Cfg = get_shared_cfg()
    status_response: TuyaResponse = get_host_status_from_cfg(cfg)
    ok: bool = await handle_status_response_ok(ctx, status_response)
    if not ok:
        return
    parsed: dict[str, Any] = get_parsed_status_from_response(status_response)
    raw_power: Any = parsed.get(CMD_HOST_PRINT_POWER_CODE)
    ldbg(f"{raw_power}Got raw host power")
    try:
        power_b: bool = bool(raw_power)
        power_text: str = "ON" if power_b else "OFF"
        await ctx.send(f"Power Status: {power_text}")
    except:
        lwarn("Failed get power text! Displaying raw value")
        await ctx.send(f"__Raw__ Power Status: {raw_power}")
    await set_bot_activity_from_power_status(ctx.bot, raw_power)
