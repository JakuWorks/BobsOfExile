from abc import ABC, abstractmethod
import logging


class MinecraftRamCounterError(Exception):
    pass


class MinecraftRamCounterCannotAllocateError(MinecraftRamCounterError):
    pass


class MinecraftRamCounterCannotDeallocateError(MinecraftRamCounterError):
    pass


class IReadableMinecraftRamCounter(ABC):
    @abstractmethod
    def allocate(self, bytes_count: int) -> None: ...
    @abstractmethod
    def deallocate(self, bytes_count: int) -> None: ...
    @abstractmethod
    def get_max_bytes(self) -> int: ...


class IMinecraftRamCounter(IReadableMinecraftRamCounter):
    @abstractmethod
    def can_allocate(self, bytes_count: int) -> bool: ...
    @abstractmethod
    def can_deallocate(self, bytes_count: int) -> bool: ...


class MinecraftRamCounterStandard(IMinecraftRamCounter):
    __slots__ = (
        "current",
        "max_bytes",
    )

    # Ints don't overflow in python like they do in other languages
    # "allocation" does not actually happen but the names are intuitive and everyone will understand their meaning
    current: int
    max_bytes: int

    def __init__(self, max_bytes: int) -> None:
        self.current = 0
        self.max_bytes = max_bytes

    def can_allocate(self, bytes_count: int) -> bool:
        return self.current + bytes_count <= self.max_bytes

    # TODO Remove :e if doesn't help readability
    def allocate(self, bytes_count: int) -> None:
        logging.debug(f"Ram counter allocating | {bytes_count=:e} | {self.current=:e}")
        new_current: int = self.current + bytes_count
        if new_current > self.max_bytes:
            raise MinecraftRamCounterCannotAllocateError(f"Goes above max {bytes_count=:e}, {self.current=:e}, {self.max_bytes=:e}") # fmt: skip
        self.current = new_current

    def can_deallocate(self, bytes_count: int) -> bool:
        return self.current - bytes_count >= 0

    def deallocate(self, bytes_count: int) -> None:
        logging.debug(
            f"Ram counter deallocating | {bytes_count=:e} | {self.current=:e}"
        )
        new_current: int = self.current - bytes_count
        if new_current < 0:
            raise MinecraftRamCounterCannotDeallocateError(f"Goes below zero {bytes_count=:e}, {self.current=:e}, {self.max_bytes=:e}") # fmt: skip
        self.current = new_current

    def get_max_bytes(self) -> int:
        return self.max_bytes


class MinecraftRamCounterDummy(IMinecraftRamCounter):
    def __init__(self) -> None:
        pass

    def can_allocate(self, bytes_count: int) -> bool:
        return True

    def allocate(self, bytes_count: int) -> None:
        pass

    def can_deallocate(self, bytes_count: int) -> bool:
        return True

    def deallocate(self, bytes_count: int) -> None:
        pass

    def get_max_bytes(self) -> int:
        return -1
