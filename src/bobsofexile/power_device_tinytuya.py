import asyncio
from typing import Mapping, Any, AsyncIterator, TypeVar, Type, Sequence
import logging

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


def ensure_existence_for_tiny_tuya_response_item(
    name: str, value: Any, existence_error_format: str
) -> Any:
    if value is None:
        raise WrongTuyaResponseFormatError(existence_error_format.format(name))
    return value


TypeToCast = TypeVar("TypeToCast", covariant=False, contravariant=False)


def ensure_existence_and_type_for_tiny_tuya_response_item(
    name: str,
    expected_type: Type[TypeToCast],
    value: Any,
    existence_error_format: str,
    type_error_format: str,
) -> TypeToCast:
    if value is None:
        raise WrongTuyaResponseFormatError(existence_error_format.format(name))
    if not isinstance(value, expected_type):
        raise WrongTuyaResponseFormatError(type_error_format.format(name))
    return value


def get_power_device_command_response_from_tuya_response(
    command_response_raw: Any,
) -> PowerDeviceCommandResponse:
    if not isinstance(command_response_raw, Mapping):
        raise WrongTuyaResponseFormatError(f"Wrong type of response")

    success: Any = command_response_raw.get(TUYA_RESPONSE_COMMAND_KEY_SUCCESS, None) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
    if success is None:
        raise WrongTuyaResponseFormatError("Missing key for success")
    if not isinstance(success, bool):
        raise WrongTuyaResponseFormatError("Wrong type of success")

    return PowerDeviceCommandResponse(success=success)


def merge_tuya_response_result_list(
    result_raw: Sequence[Any], structural_key_code: str, structural_key_value: str
) -> Mapping[str, Any]:
    existence_error_format: str = "Massing key for {0}"
    type_error_format: str = "Wrong type of {0}"

    merged: Mapping[str, Any] = dict()

    for item in result_raw:
        if not isinstance(item, dict):
            raise WrongTuyaResponseFormatError("Wrong type of result item")
        code: str = ensure_existence_and_type_for_tiny_tuya_response_item('code', str, item.get(structural_key_code, None), existence_error_format, type_error_format)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
        value: Any = ensure_existence_for_tiny_tuya_response_item('value', item.get(structural_key_value, None), existence_error_format)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
        merged[code] = value
    return merged


def get_power_device_status_from_tuya_response(
    status_raw: Any,
) -> PowerDeviceStatusResponse:
    existence_error_format: str = "Massing key for {0}"
    type_error_format: str = "Wrong type of {0}"

    if not isinstance(status_raw, Mapping):
        raise WrongTuyaResponseFormatError(type_error_format.format("response"))
    success: bool = ensure_existence_and_type_for_tiny_tuya_response_item('success', bool, status_raw.get(TUYA_RESPONSE_STATUS_KEY_SUCCESS, None), existence_error_format, type_error_format)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
    result: Sequence[Any] = ensure_existence_and_type_for_tiny_tuya_response_item('result', Sequence, status_raw.get(TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_RESULT, None), existence_error_format, type_error_format)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
    result_merged: Mapping[str, Any] = merge_tuya_response_result_list(result_raw=result, structural_key_code=TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_CODE, structural_key_value=TUYA_RESPONSE_STATUS_STRUCTURAL_KEY_VALUE)  # pyright: ignore[reportArgumentType] # fmt: skip
    turned_on: bool = ensure_existence_and_type_for_tiny_tuya_response_item('turned on', bool, result_merged.get(TUYA_RESPONSE_STATUS_RESULT_CODE_POWER_SWITCH, None), existence_error_format, type_error_format)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
    return PowerDeviceStatusResponse(success=success, turned_on=turned_on)


def get_connected_from_tuya_response(
    connected_raw: Any,
) -> PowerDeviceConnectedResponse:
    type_error_format: str = "Wrong type of {0}"
    if not isinstance(connected_raw, bool):
        raise WrongTuyaResponseFormatError(type_error_format.format("connected"))
    return PowerDeviceConnectedResponse(connected=connected_raw)


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
            response_raw: Any = self.cloud.getstatus(deviceid=self.device_id) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
        except Exception as e:  # TODO Specify exception types
            logging.error(f"Caught tuya error!", exc_info=e)
            return None
        return get_power_device_status_from_tuya_response(status_raw=response_raw)

    async def get_connected(self) -> PowerDeviceConnectedResponse | None:
        try:
            response_raw: Any = self.cloud.getconnectstatus(deviceid=self.device_id)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
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
        return PowerDeviceDetails(turned_on=status.turned_on, connected=connected.connected)

    async def power_on_async(self) -> bool:
        """
        -> success
        Does not catch tuya's errors
        """
        response_raw: Any = self.cloud.sendcommand(self.device_id, commands=self.power_on_command) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
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
        response_raw: Any = self.cloud.sendcommand(self.device_id, commands=self.power_off_command) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
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
