import sys
from common import Context
from logs import lcmd, ldbg
from OTHER_SETTINGS import (
    CMD_BOT_SHUTDOWN_ACCESS,
    CMD_BOT_SHUTDOWN_DEFAULT_TIME,
    CMD_BOT_SHUTDOWN_DEFAULT_DIVISOR,
)
from Countdowns import (
    CountdownsManager,
    GeneralDiscordCommandCountdown,
    general_try_cancel_countdowns_from_user_input,
    general_try_new_discord_command_countdown_from_user_input,
)
from bot_access import general_handle_access

_bot_shutdown_state: CountdownsManager = CountdownsManager(allow_too_big_cancellations=True)


async def bot_shutdown(
    ctx: Context,
    time: str = str(CMD_BOT_SHUTDOWN_DEFAULT_TIME),
    divisor: str = str(CMD_BOT_SHUTDOWN_DEFAULT_DIVISOR),
) -> None:
    lcmd("Command Triggered")
    global _bot_shutdown_state
    authorized: bool = await general_handle_access(ctx, CMD_BOT_SHUTDOWN_ACCESS)
    if not authorized:
        return
    countdown: GeneralDiscordCommandCountdown | None = (
        general_try_new_discord_command_countdown_from_user_input(
            time, divisor, ctx, "Bot Shutdown"
        )
    )
    if countdown is None:
        # Notifying the user is taken care of in the "general" function
        ldbg("Couldn't create countdown instance. Exiting!")
        return
    _bot_shutdown_state.add_countdown(countdown)
    countdown.start_countdown()
    success: bool = countdown.is_successful()
    if not success:
        ldbg("Bot Shutdown countdown was not successful")
        return
    await ctx.send(f"ENACTING BOT SHUTDOWN!")
    sys.exit(0)



async def bot_shutdown_cancel(ctx: Context, cancellations: str = "1") -> None:
    lcmd("Command Triggered")
    global _bot_shutdown_state
    authorized: bool = await general_handle_access(ctx, CMD_BOT_SHUTDOWN_ACCESS)
    if not authorized:
        return
    general_try_cancel_countdowns_from_user_input(
        ctx, cancellations, _bot_shutdown_state
    )