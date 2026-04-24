import abc
import asyncio
from typing import Mapping, Any, AsyncIterator
import logging

from .hardcoded import TUYA_RESPONSE_COMMAND_KEY_SUCCESS

import tinytuya  # pyright: ignore[reportMissingTypeStubs]


class PowerController(abc.ABC):
    """The errors returned by this interface depend on the used implementation!"""

    # @abc.abstractmethod
    # def power_on(self) -> bool: ...
    # @abc.abstractmethod
    # def power_off(self) -> bool: ...
    @abc.abstractmethod
    async def test_device(self) -> bool: ...
    @abc.abstractmethod
    async def power_on_async(self) -> bool: ...
    @abc.abstractmethod
    async def power_off_async(self) -> bool: ...
    @abc.abstractmethod
    async def power_on_async_with_retries(
        self, retries: int, interval: float
    ) -> AsyncIterator[bool]:
        # For type checkers
        raise NotImplementedError()
        yield 0

    @abc.abstractmethod
    async def power_off_async_with_retries(
        self, retries: int, interval: float
    ) -> AsyncIterator[bool]:
        # For type checkers
        raise NotImplementedError()
        yield 0


class WrongTinyTuyaResponseFormatError(Exception):
    pass


class TinyTuyaCommandResponse:
    """Wraps the tinytuya's response and tries to extract the values we're interested in (sometimes by making assumptions)"""

    success: bool

    def __init__(self, response_raw: Any) -> None:
        if type(response_raw) is not dict:
            raise WrongTinyTuyaResponseFormatError(
                f"Not a dict. (repr: {repr(response_raw)}) (str: {str(response_raw)}) (type: {type(response_raw)})"
            )
        if TUYA_RESPONSE_COMMAND_KEY_SUCCESS in response_raw:
            success_raw: Any = response_raw[TUYA_RESPONSE_COMMAND_KEY_SUCCESS] # pyright: ignore[reportUnknownVariableType] # fmt: skip
            if (type(success_raw) is not bool): # pyright: ignore[reportUnknownArgumentType] # fmt: skip
                raise WrongTinyTuyaResponseFormatError(f"Success is not a bool (str: {success_raw}) (type: {type(success_raw)})") # pyright: ignore[reportUnknownArgumentType] # fmt: skip
            self.success = success_raw
        else:
            logging.debug(
                f"No key ({TUYA_RESPONSE_COMMAND_KEY_SUCCESS}) in tinytuya response"
            )
            self.success = False


class TuyaPowerController(PowerController):
    """Power controller implementation for tinytuya"""

    __slots__ = (
        "access_id",
        "access_secret",
        "region",
        "device_id",
        "power_on_command",
        "power_off_command",
    )

    access_id: str
    access_secret: str
    region: str
    device_id: str
    power_on_command: Mapping[Any, Any]
    power_off_command: Mapping[Any, Any]

    def __init__(
        self,
        access_id: str,
        access_secret: str,
        region: str,
        device_id: str,
        power_on_command: Mapping[Any, Any],
        power_off_command: Mapping[Any, Any],
    ) -> None:
        self.access_id = access_id
        self.access_secret = access_secret
        self.region = region
        self.device_id = device_id
        self.power_on_command = power_on_command
        self.power_off_command = power_off_command

    async def test_device(self) -> bool:
        """
        Tests if the device can be accessed
        Catches tuya errors
        """
        cloud: tinytuya.Cloud = tinytuya.Cloud(
            apiRegion=self.region, apiSecret=self.access_secret, apiKey=self.access_id
        )

        logging.info("Testing tuya power controlling device")
        try:
            response_raw: Any = cloud.getconnectstatus(deviceid=self.device_id) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
        except Exception as e:
            logging.info(f"Caught tinytuya error: {repr(e)}", exc_info=e)
            return False
        response_raw_type: type = type(response_raw) # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType] # fmt: skip
        if (type(response_raw) is not bool):  # pyright: ignore[reportUnknownArgumentType] # fmt: skip
            logging.info(f"Got unexpected tuya response type ({response_raw_type}) (str: {str(response_raw)}) (repr: {repr(response_raw)})") # pyright: ignore[reportUnknownArgumentType] # fmt: skip
            return False
        return response_raw

    async def power_on_async(self) -> bool:
        """
        -> success
        Does not catch tinytuya's errors
        """
        cloud: tinytuya.Cloud = tinytuya.Cloud(
            apiRegion=self.region, apiSecret=self.access_secret, apiKey=self.access_id
        )
        response_raw: Any = cloud.sendcommand(self.device_id, commands=self.power_on_command) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
        try:
            response: TinyTuyaCommandResponse = TinyTuyaCommandResponse(response_raw)
        except WrongTinyTuyaResponseFormatError as e:
            logging.info(repr(e))
            return False
        logging.info(f"Got tuya response {response}")
        return response.success

    async def power_off_async(self) -> bool:
        """
        -> success
        Does not catch tinytuya's errors
        """
        cloud: tinytuya.Cloud = tinytuya.Cloud(
            apiRegion=self.region, apiSecret=self.access_secret, apiKey=self.access_id
        )
        response_raw: Any = cloud.sendcommand(self.device_id, commands=self.power_off_command) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # fmt: skip
        try:
            response: TinyTuyaCommandResponse = TinyTuyaCommandResponse(response_raw)
        except WrongTinyTuyaResponseFormatError as e:
            logging.info(repr(e))
            return False
        logging.info(f"Got tuya response {response}")
        return response.success

    async def power_on_async_with_retries(
        self, retries: int, interval: float
    ) -> AsyncIterator[bool]:
        """
        -> tuple[success, response_raw]
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
                logging.info(f"Caught tinytuya error: {repr(e)}", exc_info=e)
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
        -> tuple[success, response_raw]
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
                logging.info(f"Caught tinytuya error: {repr(e)}", exc_info=e)
                yield False
                await asyncio.sleep(interval)
                continue

            yield success
            if success:
                break
            await asyncio.sleep(interval)
        raise StopAsyncIteration
