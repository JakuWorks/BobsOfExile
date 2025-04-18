import time
from logs import ldbg


class Cd:
    cd: float
    last: float

    def __init__(self, cd: float) -> None:
        self.cd = cd
        self.last = 0

    def last_now(self) -> None:
        self.last = time.time()

    def remaining(self) -> float:
        now: float = time.time()
        elapsed: float = now - self.last
        remaining: float = self.cd - elapsed
        ldbg(f"Remaining Cooldown Time: {remaining}")
        return remaining

    def is_ready(self) -> bool:
        return self.remaining() <= 0

    def restart(self) -> None:
        self.last_now()
