from common import BotContext
from logs import lcmd
from OTHER_SETTINGS import (
    CMD_HOST_STATS_ACCESS,
    CMD_HOST_STATS_SEPARATOR,
    CMD_HOST_STATS_CPU_USAGE_INTERVAL_SECONDS,
    CMD_HOST_STATS_PROCS_LIMIT,
)
from bot_access import general_handle_access
from host_stats_helpers import (
    get_formatted_percpu_info,
    get_formatted_ram_info,
    get_formatted_swap_info,
    get_formatted_procs_info,
)

# from host_stats_helpers import


async def host_stats(ctx: BotContext) -> None:
    lcmd("Command triggered")
    authorized: bool = await general_handle_access(ctx, CMD_HOST_STATS_ACCESS)
    if not authorized:
        return
    sep: str = CMD_HOST_STATS_SEPARATOR
    start_formatting: str = "```"
    end_formatting: str = "```"

    indentation: str = " " * 4
    lines: list[str] = []
    lines.append(start_formatting)
    ram_info_text: str = get_formatted_ram_info(
        entry_separator="\n",
        separator=sep,
        entry_prefix=indentation,
        entry_suffix="",
    )
    lines.append("Ram:")
    lines.append(ram_info_text)
    swap_info_text: str = get_formatted_swap_info(
        entry_sep="\n",
        sep=sep,
        entry_prefix=indentation,
        entry_suffix="",
    )
    lines.append("Swap:")
    lines.append(swap_info_text)
    cpu_cores_info_text: str = get_formatted_percpu_info(
        sort=True,
        use_interval=CMD_HOST_STATS_CPU_USAGE_INTERVAL_SECONDS,
        entries_sep="\n",
        sep=sep,
        sort_by_use=True,
        entry_prefix=indentation,
        entry_suffix="",
        sort_reverse=True,
    )
    lines.append("Cpu Cores:")
    lines.append(cpu_cores_info_text)
    lines.append("Process:")
    # TODO entries limit setting
    procs_info_text: str = get_formatted_procs_info(
        entries_limit=CMD_HOST_STATS_PROCS_LIMIT,
        uses_interval=1,
        entries_separator="\n",
        sep=sep,
        entry_prefix=indentation,
        entry_suffix="",
    )
    lines.append(procs_info_text)

    lines.append(end_formatting)
    t: str = "\n".join(lines)
    await ctx.send(t)
