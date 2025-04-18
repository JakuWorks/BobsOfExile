from typing import Any, KeysView
import tinytuya  # type: ignore
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
)
from common import (
    TuyaResponse,
    TuyaCloudInfo,
    TuyaResponseKeys,
    TuyaResultEntry,
    TuyaResultKeys,
    CfgMasterOptions,
)
from logs import ldbg, lwarn
from cfg import Cfg
from tuya_helpers import (
    get_cloud_info_from_cfg,
    get_cloud_instance,
)


def check_status_entry(entry: TuyaResultEntry) -> bool:
    logs_infix: str = f"Entry: {entry}{s}"
    ldbg(f"{logs_infix}Checking status entry for correctness")
    warn_infix: str = f"Got incorrect format in tuya's status response entry!{s}"
    keys: KeysView[str] = entry.keys()
    want_l: int = 2
    l: int = len(keys)
    if len(keys) != want_l:
        lwarn(f"{logs_infix}{warn_infix}Wrong dict keys count ({l})")
        return False
    if TuyaResultKeys.CODE.value not in entry:
        lwarn(f"{logs_infix}{warn_infix}Key not found ({TuyaResultKeys.CODE.value})")
        return False
    if TuyaResultKeys.VALUE.value not in entry:
        lwarn(f"{warn_infix}Key not found ({TuyaResultKeys.VALUE.value})")
        return False
    ldbg(f"{logs_infix}Correct")
    return True


def parse_status(status: list[TuyaResultEntry]) -> dict[str, Any]:
    ldbg("Parsing tuya's status response")
    merged: dict[str, Any] = {}
    for status_entry in status:
        correct: bool = check_status_entry(status_entry)
        if not correct:
            lwarn("Status response entry incorrect format! Skipping!")
            continue
        name: str = status_entry[TuyaResultKeys.CODE.value]
        value: Any = status_entry[TuyaResultKeys.VALUE.value]
        merged[name] = value
    return merged


def get_host_status(cloud_info: TuyaCloudInfo, dev_id: str) -> TuyaResponse:
    ldbg("Getting host status")
    region: str = cloud_info["region"]
    access_id: str = cloud_info["access_id"]
    access_secret: str = cloud_info["access_secret"]
    cloud: tinytuya.Cloud = get_cloud_instance(
        region=region, access_id=access_id, access_secret=access_secret
    )
    status_response: TuyaResponse = cloud.getstatus(dev_id)  # type: ignore
    return status_response


def get_host_status_from_cfg(cfg: Cfg) -> TuyaResponse:
    # This function exists only to reduce boilerplate
    cloud_info: TuyaCloudInfo = get_cloud_info_from_cfg(cfg)
    dev_id: str = cfg.get_master_str_data(
        CfgMasterOptions.TUYA_SWITCH_DEVICE_ID.value, True
    )
    status_response: TuyaResponse = get_host_status(cloud_info, dev_id)
    return status_response


def get_parsed_status_from_response(response: TuyaResponse) -> dict[str, Any]:
    # This function exists only to reduce boilerplate
    status: list[TuyaResultEntry] = response[TuyaResponseKeys.RESULT.value]
    parsed: dict[str, Any] = parse_status(status)
    return parsed