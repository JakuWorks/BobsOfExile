from typing import Any
from logs import levent


# Blatantly copied from the Main bot
async def on_error(method: str, *args: Any, **kwargs: Any) -> None:
    levent("GOT AN ERROR!")
    # Just re-raising. It's just better to let it print in the console
    raise
