from common import BotContext, CfgMasterOptions, TuyaCloudInfo, TuyaCommands
from OTHER_SETTINGS import (
    CMD_HOST_POWER_ON_ACCESS,
    CMD_HOST_POWER_OFF_ACCESS,
    CMD_HOST_POWER_COOLDOWN,
    CMD_HOST_POWER_ON_TUYA_CMD,
    CMD_HOST_POWER_OFF_TUYA_CMD,
)
from logs import lcmd
from cfg import get_shared_cfg, Cfg
from bot_activity import set_bot_activity_from_power_status
from bot_access import generic_handle_access
from tuya_helpers import send_cmd, get_cloud_info_from_cfg
from Cooldown import Cd


_SHARED_CD: Cd = Cd(CMD_HOST_POWER_COOLDOWN)


async def generic_host_power_action(ctx: BotContext, cmds: TuyaCommands) -> bool:
    # -> success
    global _SHARED_CD
    cfg: Cfg = get_shared_cfg()
    cloud_info: TuyaCloudInfo = get_cloud_info_from_cfg(cfg)
    dev_id: str = cfg.get_master_str_data(
        CfgMasterOptions.TUYA_SWITCH_DEVICE_ID.value, True
    )

    cooldown: Cd = _SHARED_CD
    success: bool = await send_cmd(
        cloud_info=cloud_info, dev_id=dev_id, ctx=ctx, cmds=cmds, cooldown=cooldown
    )
    return success


async def host_power_on(ctx: BotContext) -> None:
    """Turn on host's power. Alias: host-on"""
    lcmd("Command Triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_HOST_POWER_ON_ACCESS)
    if not authorized:
        return
    success: bool = await generic_host_power_action(ctx, CMD_HOST_POWER_ON_TUYA_CMD)
    if success:
        await set_bot_activity_from_power_status(ctx.bot, True)


async def host_power_off(ctx: BotContext) -> None:
    """Turn off host's power. Alias: host-off"""
    lcmd("Command Triggered")
    authorized: bool = await generic_handle_access(ctx, CMD_HOST_POWER_OFF_ACCESS)
    if not authorized:
        return
    success: bool = await generic_host_power_action(ctx, CMD_HOST_POWER_OFF_TUYA_CMD)
    if success:
        await set_bot_activity_from_power_status(ctx.bot, False)
