from common import Context, Platform
from logs import lcmd, ldbg, lwarn
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
    CMD_HOST_SHUTDOWN_ACCESS,
    CMD_HOST_SHUTDOWN_CANCEL_ACCESS,
    CMD_HOST_SHUTDOWN_DEFAULT_TIME,
    CMD_HOST_SHUTDOWN_DEFAULT_DIVISOR,
    CMD_HOST_SHUTDOWN_CMD_LINUX,
)
from platforms import get_platform
from Countdowns import (
    CountdownsManager,
    GeneralDiscordCommandCountdown,
    general_try_cancel_countdowns_from_user_input,
    general_try_new_discord_command_countdown_from_user_input,
)
from bot_access import general_handle_access


_host_shutdown_countdown_manager: CountdownsManager = CountdownsManager(
    allow_too_big_cancellations=True
)


async def host_shutdown(
    ctx: Context,
    time: str = str(CMD_HOST_SHUTDOWN_DEFAULT_TIME),
    divisor: str = str(CMD_HOST_SHUTDOWN_DEFAULT_DIVISOR),
) -> None:
    lcmd("Command Triggered")
    global _host_shutdown_countdown_manager
    authorized: bool = await general_handle_access(ctx, CMD_HOST_SHUTDOWN_ACCESS)
    if not authorized:
        return
    countdown: GeneralDiscordCommandCountdown | None = (
        general_try_new_discord_command_countdown_from_user_input(
            time, divisor, ctx, "Host Shutdown"
        )
    )
    if countdown is None:
        # Notifying the user is taken care of in the "general" function
        ldbg("Couldn't create countdown instance. Exiting!")
        return
    _host_shutdown_countdown_manager.add_countdown(countdown)
    countdown.start_countdown()
    success: bool = countdown.is_successful()
    if not success:
        ldbg("Host Shutdown countdown was not successful")
        return
    syst: Platform = get_platform()
    if syst == Platform.LINUX:
        logs_infix: str = f"{CMD_HOST_SHUTDOWN_CMD_LINUX=}{s}"
        ldbg(f"{logs_infix}Shutting down!")
        await ctx.send(f"ENACTING HOST SHUTDOWN!")
    else:
        await ctx.send(f"Cannot shut down host! Unsupported platform :sob:")
        lwarn("Unsupported platform! Cannot shut down host")


async def host_shutdown_cancel(ctx: Context, cancellations: str = "1") -> None:
    lcmd("Command Triggered")
    global _host_shutdown_countdown_manager
    authorized: bool = await general_handle_access(ctx, CMD_HOST_SHUTDOWN_CANCEL_ACCESS)
    if not authorized:
        return
    general_try_cancel_countdowns_from_user_input(
        ctx, cancellations, _host_shutdown_countdown_manager
    )