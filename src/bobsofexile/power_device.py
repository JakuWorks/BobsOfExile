import abc
from typing import AsyncIterator



class PowerDeviceCommandResponse:
    __slots__ = ("success", )

    success: bool

    def __init__(self, success: bool) -> None:
        self.success = success


class PowerDeviceStatusResponse:
    __slots__ = ("success", "turned_on")

    success: bool
    turned_on: bool

    def __init__(self, success: bool, turned_on: bool) -> None:
        self.success = success
        self.turned_on = turned_on


class PowerDeviceConnectedResponse:
    __slots__ = ("connected", )

    connected: bool
    
    def __init__(self, connected: bool) -> None:
        self.connected = connected

class PowerDeviceDetails:
    __slots__ = ("turned_on", "connected")

    turned_on: bool
    connected: bool

    def __init__(self, turned_on: bool, connected: bool) -> None:
        self.turned_on = turned_on
        self.connected = connected


class PowerController(abc.ABC):
    """The errors returned by this interface depend on the used implementation!
    Some methods may be more efficient than others, it depends on the implementation"""

    # @abc.abstractmethod
    # def power_on(self) -> bool: ...
    # @abc.abstractmethod
    # def power_off(self) -> bool: ...
    @abc.abstractmethod
    async def get_status(self) -> PowerDeviceStatusResponse | None: ...
    @abc.abstractmethod
    async def get_connected(self) -> PowerDeviceConnectedResponse | None: ...
    @abc.abstractmethod
    async def get_details(self) -> PowerDeviceDetails | None: ...
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