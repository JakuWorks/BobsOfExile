from platforms import Platform, all_platforms
from commands_helpers import CommandsRegister
from commands.host_stats import host_stats
from commands.bot_shutdowns import bot_shutdown, bot_shutdown_cancel
from commands.host_reboots import host_reboot, host_reboot_cancel
from commands.host_shutdowns import host_shutdown, host_shutdown_cancel
from commands.add import add
from commands.echo import echo
from commands.hi import hi

# fmt: off


# tuple[enabled, name, aliases, supported_platforms, func]
COMMANDS: CommandsRegister = [
    (True, "hi", ["hello"], all_platforms, hi),
    (True, "echo", [], all_platforms, echo),
    (True, "add", [], all_platforms, add),
    (True, "host-stats", ["host-stat", "host-s"], all_platforms, host_stats),
    (True, "bot-shutdown", ["bot-shut"], all_platforms, bot_shutdown),
    (True, "bot-shutdown-cancel", ["bot-shut-c"], all_platforms, bot_shutdown_cancel),
    (True, "host-shutdown", ["host-shut"], [Platform.LINUX], host_shutdown),
    (True, "host-shutdown-cancel", ["host-shut-c"], [Platform.LINUX], host_shutdown_cancel),
    (True, "host-reboot", ["host-reb"], [Platform.LINUX], host_reboot),
    (True, "host-reboot-cancel", ["host-reb-c"], [Platform.LINUX], host_reboot_cancel),
]
