from abc import ABC, abstractmethod


class ILongResponse(ABC):
    @abstractmethod
    async def start(self) -> None: ...
    @abstractmethod
    async def add_text(self, text: str) -> None: ...
    @abstractmethod
    async def add_line(self, line: str) -> None: ...


class IResponder(ABC):
    @abstractmethod
    async def respond(self, msg: str) -> None: ...
    @abstractmethod
    def new_long_response(self, init_msg: str | None) -> ILongResponse: ...
