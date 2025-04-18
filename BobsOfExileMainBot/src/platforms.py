from common import Platform
import platform
import functools
from logs import ldbg
from OTHER_SETTINGS import LOGS_SEPARATOR as s


all_platforms: set[Platform] = set(iter(Platform))


@functools.lru_cache(maxsize=1, typed=True)
def get_platform() -> Platform:
    system: str = platform.system()
    identified: Platform
    if system == "Windows":
        identified = Platform.WINDOWS
    elif system == "Linux":
        identified = Platform.LINUX
    elif system == "Darwin":
        identified = Platform.MACOS
    else:
        identified = Platform.UNKNOWN
    logs_infix: str = f"{identified.value=}{s}"
    ldbg(f"{logs_infix}Identified OS")
    return identified
