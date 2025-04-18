from typing import Collection
from collections import deque
from common import Context
from primitive_helpers import deque_pop_left_many, deque_pop_many
from async_helpers import synchronize_run
import asyncio
import math
import enum
from logs import ldbg
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
)

# TODO - Perhaps possible race bug when - after adding to the manager, the 


# I experimented and attempted to decouple methods within this class as much as possible (sadly sacrificing readability). It works so I left it this way
class BaseCountdown:
    # An instance of this class represents a singular countdown
    # Mostly for subclassing
    remaining: float
    cancelled: bool
    started: bool
    ended: bool

    def __init__(self, duration: float) -> None:
        self.remaining = duration
        self.started = False
        self.cancelled = False
        self.ended = False

    def started_hook(self) -> None:
        self.started_notify()

    def started_notify(self) -> None:
        pass

    def cancel_hook(self) -> None:
        # Executed as soon as it's cancelled via .cancel()
        self.cancel_notify()

    def cancel_notify(self) -> None:
        pass

    def final_cancelled_hook(self) -> None:
        # Executed after the sleep is over
        self.final_cancelled_notify()

    def final_cancelled_notify(self) -> None:
        pass

    def success_hook(self) -> None:
        self.success_notify()

    def success_notify(self) -> None:
        pass

    def step_begin_hook(self) -> None:
        self.step_begin_notify()

    def step_begin_notify(self) -> None:
        pass

    def get_countdown_info_str(self) -> str:
        t: str = (
            f"Remaining: {self.remaining}{s}"
            f"Started: {self.started}{s}"
            f"Ended: {self.ended}{s}"
            f"Cancelled: {self.cancelled}"
        )
        return t

    async def sleep(self, t: float) -> None:
        assert t > 0, "Cannot sleep for 0 or less seconds here"
        await asyncio.sleep(t)

    def determine_next_step_sleep(self, remaining: float) -> float:
        # One step takes up the entire duration by default
        return remaining

    def cancel(self) -> None:
        self.cancel_hook()
        self.cancelled = True

    async def step(self) -> None:
        self.step_begin_hook()
        await self.step_sleep()

    async def step_sleep(self) -> None:
        step_sleep: float = self.determine_next_step_sleep(self.remaining)
        await self.sleep(step_sleep)
        self.remaining = self.remaining - step_sleep

    async def countdown_loop(self) -> None:
        while True:
            if self.remaining <= 0 or self.cancelled:
                self.ended = True
                break
            await self.step()

    def ensure_not_started(self) -> None:
        if self.started:
            raise RuntimeError("Tried starting countdown more than once")

    def ensure_can_start(self) -> None:
        self.ensure_not_started()

    def enact_the_over_hooks(self) -> None:
        assert self.is_over(), "Must be over to enact the over hooks"
        if self.cancelled:
            self.final_cancelled_hook()
            return
        if self.ended == True:
            self.success_hook()
            return
        raise RuntimeError("Incorrect state when enacting the over hooks")

    def is_over(self) -> bool:
        return self.ended or self.cancelled

    def is_successful(self) -> bool:
        if not self.is_over():
            raise RuntimeError("Must be over to determine success")
        return not self.cancelled

    def start_countdown(self) -> None:
        # -> was_not_cancelled
        ldbg("Started Countdown")
        self.ensure_can_start()
        self.started_hook()
        self.started = True
        synchronize_run(self.countdown_loop())
        self.ended = True
        self.enact_the_over_hooks()
        ldbg("Finished Countdown")


class ManageableCountdown(BaseCountdown):
    in_manager: bool

    def __init__(self, duration: float) -> None:
        super().__init__(duration)
        self.in_manager = False


class CancelDirection(enum.Enum):
    FROM_LEFT = "left"
    FROM_RIGHT = "right"


class CountdownsManager:
    active: deque[ManageableCountdown]
    allow_too_big_cancellations: bool

    def __init__(self, allow_too_big_cancellations: bool) -> None:
        self.active: deque[ManageableCountdown] = deque()
        self.allow_too_big_cancellations = allow_too_big_cancellations

    def to_cleanup(self, countdown: ManageableCountdown) -> bool:
        return countdown.is_over() or not countdown.started

    def cleanup(self) -> None:
        new: deque[ManageableCountdown] = deque(
            countdown for countdown in self.active if not self.to_cleanup(countdown)
        )
        self.active = new

    def ensure_countdown_in_no_manager(self, countdown: ManageableCountdown) -> None:
        if countdown.in_manager:
            raise RuntimeError("A countdown can be part of only one manager")

    def add_countdown(self, countdown: ManageableCountdown) -> None:
        self.active.append(countdown)

    def add_countdowns(self, countdowns: Collection[ManageableCountdown]) -> None:
        self.active.extend(countdowns)

    def adjust_cancellations(self, cancellations: int) -> int:
        if self.allow_too_big_cancellations:
            return min(len(self.active), cancellations)
        return cancellations

    def ensure_correct_cancellations(self, cancellations: int) -> None:
        active_len: int = len(self.active)
        if cancellations > active_len:
            logs_infix: str = f"{cancellations=}{s}{active_len=}{s}"
            raise RuntimeError(f"{logs_infix}Cancelling too many countdowns!")
    
    def _cancels(self, cancels: Collection[ManageableCountdown]) -> None:
        for to_cancel in cancels:
            to_cancel.cancel()

    def cancel_countdowns(self, cancellations: int, direction: CancelDirection) -> None:
        self.cleanup()
        c = self.adjust_cancellations(cancellations)
        self.ensure_correct_cancellations(c)
        if direction.value == CancelDirection.FROM_LEFT.value:
            self._cancels(deque_pop_left_many(self.active, cancellations))
            return
        if direction.value == CancelDirection.FROM_RIGHT.value:
            self._cancels(deque_pop_many(self.active, cancellations))
            return
        logs_infix: str = f"{direction.value=}{s}"
        raise RuntimeError(f"{logs_infix}Wrong direction!")


class GeneralDiscordCommandCountdown(ManageableCountdown):
    divisor: float
    action_name: str
    ctx: Context

    def __init__(
        self,
        duration: float,
        divisor: float,
        ctx: Context,
        action_name: str,
    ) -> None:
        super().__init__(duration)
        self.divisor = divisor
        self.ctx = ctx
        self.action_name = action_name

    def send_msg_in_ctx(self, t: str) -> None:
        synchronize_run(self.ctx.send(t))

    def remaining_str(self, remaining: float) -> str:
        return f"{remaining:.1f}"

    def started_notify(self) -> None:
        logs_infix: str = f"{self.action_name=}{s}{self.remaining=}{s}{self.divisor=}{s}"
        ldbg(f"{logs_infix}Started Countdown")

    def success_notify(self) -> None:
        logs_infix: str = f"{self.action_name=}{s}{self.remaining=}{s}{self.divisor=}{s}"
        ldbg(f"{logs_infix}Successfully Finished Countdown")

    def cancel_notify(self) -> None:
        logs_infix: str = f"{self.action_name=}{s}{self.remaining=}{s}{self.divisor=}{s}"
        ldbg(f"{logs_infix}Cancelled Countdown")
        self.send_msg_in_ctx(f"{self.action_name} - Cancelled")

    def final_cancelled_notify(self) -> None:
        logs_infix: str = f"{self.action_name=}{s}{self.remaining=}{s}{self.divisor=}{s}"
        ldbg(f"{logs_infix}Final Countdown Cancellation")

    def step_begin_notify(self) -> None:
        logs_infix: str = f"{self.action_name=}{s}{self.remaining=}{s}{self.divisor=}{s}"
        ldbg(f"{logs_infix}Countdown Step")
        remaining_str = self.remaining_str(self.remaining)
        t: str = f"{self.action_name} in T - {remaining_str}"
        self.send_msg_in_ctx(t)

    def determine_next_step_sleep(self, remaining: float) -> float:
        ret: float = math.ceil(remaining / self.divisor)
        return ret


def general_try_new_discord_command_countdown_from_user_input(
    duration: str,
    divisor: str,
    ctx: Context,
    action_name: str,
) -> GeneralDiscordCommandCountdown | None:
    duration_p: float | None = parse_user_duration(duration)
    if duration_p is None or duration_p < 0:
        t: str = "Incorrect time!"
        synchronize_run(ctx.send(t))
        return None
    divisor_p: float | None = parse_user_divisor(divisor)
    if divisor_p is None or divisor_p <= 0:
        t: str = "Incorrect divisor!"
        synchronize_run(ctx.send(t))
        return None
    return GeneralDiscordCommandCountdown(duration_p, divisor_p, ctx, action_name)


def general_try_cancel_countdowns_from_user_input(
    ctx: Context,
    cancellations: str,
    manager: CountdownsManager,
) -> None:
    cancellations_p: int | None = parse_user_cancellations(cancellations)
    if cancellations_p is None or cancellations_p < 1:
        t: str = "Incorrect cancellations"
        synchronize_run(ctx.send(t))
        return
    # TODO SETTING FOR DIRECTION
    manager.cancel_countdowns(cancellations_p, CancelDirection.FROM_LEFT)


def parse_user_duration(duration: str) -> float | None:
    if duration.lower() == "now":
        return 0
    try:
        return float(duration)
    except:
        return None


def parse_user_divisor(divisor: str) -> float | None:
    try:
        return float(divisor)
    except:
        return None


def parse_user_cancellations(cancellations: str) -> int | None:
    try:
        return int(cancellations)
    except:
        return None