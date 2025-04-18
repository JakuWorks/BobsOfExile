from typing import Any
from logs import levent


async def on_error(method: str, *args: Any, **kwargs: Any) -> None:
    levent("GOT AN ERROR!")
    # Just re-raising :)
    raise