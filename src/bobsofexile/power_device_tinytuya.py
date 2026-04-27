import asyncio
from typing import Mapping, Any, AsyncIterator, Sequence
import logging

from .main_convenience import ensure_existence_and_type, ensure_existence
from .hardcoded import (
    TUYA_RESPONSE_COMMAND_KEY_SUCCESS,
    TUYA_RESPONSE_STATUS_RESULT_CODE_POWER_SWITCH,
    TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_CODE,
    TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_RESULT,
    TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_VALUE,
    TUYA_RESPONSE_STATUS_KEY_SUCCESS,
)
from .power_device import (
    PowerController,
    PowerDeviceCommandResponse,
    PowerDeviceStatusResponse,
    PowerDeviceDetails,
    PowerDeviceConnectedResponse,
)

import tinytuya  # pyright: ignore[reportMissingTypeStubs]


class WrongTuyaResponseFormatError(Exception):
    pass


def get_power_device_command_response_from_tuya_response(
    command_response_raw: Any,
) -> PowerDeviceCommandResponse:
    response: Mapping[Any, Any] = ensure_existence_and_type('response', Mapping, command_response_raw,                WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    success: bool = ensure_existence_and_type('success', bool, response.get(TUYA_RESPONSE_COMMAND_KEY_SUCCESS, None), WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    return PowerDeviceCommandResponse(success=success)


def merge_tuya_response_result_list(
    result_raw: Sequence[Any], structural_key_code: str, structural_key_value: str
) -> Mapping[str, Any]:
    merged: Mapping[str, Any] = dict()

    for item_raw in result_raw:
        item: Mapping[Any, Any] = ensure_existence_and_type('result item', Mapping, item_raw,   WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
        code: str = ensure_existence_and_type('code', str, item.get(structural_key_code, None), WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
        value: Any = ensure_existence('value', item.get(structural_key_value, None),            WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
        merged[code] = value
    return merged


def get_power_device_status_from_tuya_response(
    status_raw: Any,
) -> PowerDeviceStatusResponse:
    status: Mapping[Any, Any] = ensure_existence_and_type('raw status', Mapping, status_raw,                                               WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    success: bool = ensure_existence_and_type('success', bool, status.get(TUYA_RESPONSE_STATUS_KEY_SUCCESS, None),                         WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    result: Sequence[Any] = ensure_existence_and_type('result', Sequence, status.get(TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_RESULT, None),    WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    result_merged: Mapping[str, Any] = merge_tuya_response_result_list(result_raw=result, structural_key_code=TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_CODE, structural_key_value=TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_VALUE)  # pyright: ignore[reportArgumentType]  # fmt: skip
    turned_on: bool = ensure_existence_and_type('turned on', bool, result_merged.get(TUYA_RESPONSE_STATUS_RESULT_CODE_POWER_SWITCH, None), WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    return PowerDeviceStatusResponse(success=success, turned_on=turned_on)


def get_connected_from_tuya_response(
    connected_raw: Any,
) -> PowerDeviceConnectedResponse:
    connected: bool = ensure_existence_and_type('connected', bool, connected_raw, WrongTuyaResponseFormatError, WrongTuyaResponseFormatError)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
    return PowerDeviceConnectedResponse(connected=connected)


class TuyaPowerController(PowerController):
    """Power controller implementation for tuya"""

    __slots__ = (
        "cloud",
        "device_id",
        "power_on_command",
        "power_off_command",
    )

    cloud: tinytuya.Cloud
    device_id: str
    power_on_command: Mapping[Any, Any]
    power_off_command: Mapping[Any, Any]

    def __init__(
        self,
        cloud: tinytuya.Cloud,
        device_id: str,
        power_on_command: Mapping[Any, Any],
        power_off_command: Mapping[Any, Any],
    ) -> None:
        self.cloud = cloud
        self.device_id = device_id
        self.power_on_command = power_on_command
        self.power_off_command = power_off_command

    async def get_status(self) -> PowerDeviceStatusResponse | None:
        """
        Catches tuya errors
        """
        try:
            response_raw: Any = self.cloud.getstatus(deviceid=self.device_id)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
        except Exception as e:  # TODO Specify exception types
            logging.error(f"Caught tuya error!", exc_info=e)
            return None
        return get_power_device_status_from_tuya_response(status_raw=response_raw)

    async def get_connected(self) -> PowerDeviceConnectedResponse | None:
        try:
            response_raw: Any = self.cloud.getconnectstatus(deviceid=self.device_id)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
        except Exception as e:  # TODO Specify exception types
            logging.error(f"Caught tuya error!", exc_info=e)
            return None
        return get_connected_from_tuya_response(response_raw)

    async def get_details(self) -> PowerDeviceDetails | None:
        status: PowerDeviceStatusResponse | None = await self.get_status()
        connected: PowerDeviceConnectedResponse | None = await self.get_connected()
        if status is None:
            return None
        if connected is None:
            return None
        return PowerDeviceDetails(
            turned_on=status.turned_on, connected=connected.connected
        )

    async def power_on_async(self) -> bool:
        """
        -> success
        Does not catch tuya's errors
        """
        response_raw: Any = self.cloud.sendcommand(self.device_id, commands=self.power_on_command)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
        response: PowerDeviceCommandResponse = (
            get_power_device_command_response_from_tuya_response(response_raw)
        )
        logging.info(f"Got tuya response {response}")
        return response.success

    async def power_off_async(self) -> bool:
        """
        -> success
        Does not catch tuya's errors
        """
        response_raw: Any = self.cloud.sendcommand(self.device_id, commands=self.power_off_command)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # fmt: skip
        response: PowerDeviceCommandResponse = (
            get_power_device_command_response_from_tuya_response(response_raw)
        )
        logging.info(f"Got tuya response {response}")
        return response.success

    async def power_on_async_with_retries(
        self, retries: int, interval: float
    ) -> AsyncIterator[bool]:
        """
        Stops iterating after yielding True or after exhausting retries.
        Catches tuya errors
        """
        while True:
            if retries < 0:
                break
            retries = -1

            try:
                success: bool = await self.power_on_async()
            except Exception as e:  # TODO Specify exception types
                logging.error(f"Caught tuya error!", exc_info=e)
                yield False
                await asyncio.sleep(interval)
                continue

            yield success
            if success:
                break
            await asyncio.sleep(interval)
        raise StopAsyncIteration

    async def power_off_async_with_retries(
        self, retries: int, interval: float
    ) -> AsyncIterator[bool]:
        """
        Stops iterating after yielding True or after exhausting retries.
        Catches tuya errors
        """
        while True:
            if retries < 0:
                break
            retries = -1

            try:
                success: bool = await self.power_off_async()
            except Exception as e:  # TODO Specify exception types
                logging.error(f"Caught tuya error!", exc_info=e)
                yield False
                await asyncio.sleep(interval)
                continue

            yield success
            if success:
                break
            await asyncio.sleep(interval)
        raise StopAsyncIteration
