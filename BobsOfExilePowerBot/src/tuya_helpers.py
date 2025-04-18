from typing import Any, cast
import math
import functools
import tinytuya  # type: ignore
from common import (
    BotContext,
    TuyaCloudInfo,
    TuyaCommands,
    TuyaResponse,
    TuyaResponseKeys,
)
from OTHER_SETTINGS import LOGS_SEPARATOR as s
from logs import ldbg, lwarn, get_secret_text as gs, limit_length as lm
from cfg import Cfg, CfgMasterOptions
from Cooldown import Cd


# cd -> cooldown


async def handle_cd_is_ready(ctx: BotContext, cooldown: Cd) -> bool:
    """Also informs the "chat" about the cd state"""
    remaining: float = cooldown.remaining()
    if remaining <= 0:
        ldbg("Not on cd")
        return True
    else:
        ldbg("Still on cd")
        await ctx.send(f"On cooldown! ({math.ceil(remaining)}s)")
        return False


# Cache size 1 because (so far) there's only 1 config file
@functools.lru_cache(maxsize=1, typed=True)
def get_cloud_info_from_cfg(cfg: Cfg) -> TuyaCloudInfo:
    ldbg("Getting tuya cloud information from the cfg")
    region: str = cfg.get_master_str_data(CfgMasterOptions.TUYA_REGION.value, True)
    access_id: str = cfg.get_master_str_data(
        CfgMasterOptions.TUYA_ACCESS_ID.value, True
    )
    access_secret: str = cfg.get_master_str_data(
        CfgMasterOptions.TUYA_ACCESS_SECRET.value, True
    )
    info: TuyaCloudInfo = {
        "region": region,
        "access_id": access_id,
        "access_secret": access_secret,
    }
    return info


async def send_cmd(
    cloud_info: TuyaCloudInfo,
    dev_id: str,
    ctx: BotContext,
    cmds: TuyaCommands,
    cooldown: Cd | None,
) -> bool:
    # -> Success
    """
    Creates a tinytuya.Cloud instance and sends a command to a device
    on the condition that the cooldown has passed (if a CdCmd instance is not none)
    Keeps the discord "chat" informed through the context
    Also manages the cooldown instance
    """
    region: str = cloud_info["region"]
    access_id: str = cloud_info["access_id"]
    access_secret: str = cloud_info["access_secret"]

    # The infix is really long so it's not going to be used much
    logs_infix: str = (
        f"Reg: {lm(gs(region))}"
        f"{s}AccessID: {lm(gs(access_id))}"
        f"{s}AccessSecret: {lm(gs(access_secret))}"
        f"{s}DevID: {lm(gs(dev_id))}"
        f"{s}Cmds: {cmds}{s}"
    )
    ldbg(f"{logs_infix}Func triggered")

    has_cd: bool = cooldown is not None
    if has_cd:
        is_ready: bool = await handle_cd_is_ready(ctx, cooldown)
        if not is_ready:
            return False

    cloud: tinytuya.Cloud = get_cloud_instance(
        region=region, access_id=access_id, access_secret=access_secret
    )
    ldbg("Sending tuya command")
    response: dict[str, Any] | None = cloud.sendcommand(dev_id, cmds)
    successful: bool 
    if response is None:
        lwarn("Didn't receive a response")
        await ctx.send(
            "Didn't receive a response from the server, however your command may have still worked,"
        )
        successful = True
    elif not isinstance(response, dict):
        lwarn("Wrong response format")
        await ctx.send(
            "The response from the server was in the wrong format,"
            "however your command may have still worked."
        )
        successful = True
    else:
        response = cast(dict[str, Any], response) # ASSUMING THE KEY AND VALUE TYPES
        ok: bool = get_response_ok(response)
        if ok:
            ldbg(f"Success")
            await ctx.send("Successfully performed action!")
            successful = True
        else:
            lwarn(f"Failure!{s}{str(response)}")
            await ctx.send(f"Failure at performing action!\n```\n{str(response)}\n```")
            successful = False
    if successful and has_cd:
        cooldown.restart()
    return successful


@functools.lru_cache(maxsize=1, typed=True)
def get_cloud_instance(
    region: str, access_id: str, access_secret: str
) -> tinytuya.Cloud:
    # "simple" because not all arguments that can go into the initial function are supported by our arguments
    # not using a typeddict because lru_cache wants the func args to be hashable
    ldbg("Creating tuya cloud instance (cached)")
    cloud = tinytuya.Cloud(apiKey=access_id, apiSecret=access_secret, apiRegion=region)
    return cloud


def get_response_ok(response: TuyaResponse) -> bool:
    success_k: str = TuyaResponseKeys.SUCCESS.value
    ok: bool | None | Any = response.get(success_k)
    if ok is None:
        # Not a warning, because some non-successful responses simply don't have it
        ldbg(f"Tuya's response didn't contain a field \"{success_k}\"!")
        return False
    if not isinstance(ok, bool):
        lwarn(f'Tuya\'s response got incorrect type at field "{success_k}"')
        return False
    return True
