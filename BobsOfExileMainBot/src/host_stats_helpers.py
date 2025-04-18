from typing import Callable, Any, TypeGuard, Collection
from common import (
    SupportsGetItem,
    SupportsRichComparison_,
    RamInfo,
    SwapInfo,
    PercpuFreqUse,
    PercpuFreqs,
    PercpuFreqsUses,
    PercpuUses,
    ProcInfo,
)
import time
import math
import psutil
from psutil._common import scpufreq # type: ignore

# TODO -  replace scpufreq with my own "class" perhaps?
from primitive_helpers import have_same_keys
from string_helpers import pad_left_to_length
from logs import ldbg, lwarn
from OTHER_SETTINGS import (
    LOGS_SEPARATOR as s,
    CMD_HOST_STATS_CPU_ENTRY_CURRENT_DECIMALS,
    CMD_HOST_STATS_CPU_ENTRY_MAX_DECIMALS,
    CMD_HOST_STATS_CPU_ENTRY_USE_DECIMALS,
)

# NOTE:
# Many words in this file have been abbreviated
# use - usage
# uses - usages
# proc - process
# procs - processes
# and so on...


_BYTES_IN_GB: int = 1073741824  # 1024 ** 3


# MEM & SWAP =================================================


# Ram and swap functions are placed parallel due to their similarities


def check_ram_info(mem: Any) -> TypeGuard[RamInfo]:
    if not hasattr(mem, "total") or not isinstance(mem.total, int):
        return False
    if not hasattr(mem, "available") or not isinstance(mem.available, int):
        return False
    if not hasattr(mem, "percent") or not isinstance(mem.percent, float):
        return False
    if not hasattr(mem, "used") or not isinstance(mem.used, int):
        return False
    if not hasattr(mem, "free") or not isinstance(mem.free, int):
        return False
    return True


def check_swap_info(mem: Any) -> TypeGuard[SwapInfo]:
    if not hasattr(mem, "total") or not isinstance(mem.total, int):
        return False
    if not hasattr(mem, "percent") or not isinstance(mem.percent, float):
        return False
    if not hasattr(mem, "used") or not isinstance(mem.used, int):
        return False
    if not hasattr(mem, "free") or not isinstance(mem.free, int):
        return False
    return True


def get_ram_info() -> RamInfo:
    mem: Any = psutil.virtual_memory()
    valid: bool = check_ram_info(mem)
    if not valid:
        raise RuntimeError("Got missing attributes and/or invalid types when trying to get ram info")
    return mem


def get_swap_info() -> SwapInfo:
    mem: Any = psutil.swap_memory()
    valid: bool = check_swap_info(mem)
    if not valid:
        raise RuntimeError("Got missing attributes and/or invalid types when trying to get swap info")
    return mem


def get_formatted_ram_info(
    entry_separator: str, separator: str, entry_prefix: str, entry_suffix: str
) -> str:
    logs_infix: str = f"{entry_separator=}{s}{separator=}{s}{entry_prefix=}{s}{entry_suffix=}{s}"
    ldbg(f"{logs_infix}Getting formatted ram info")
    mem: RamInfo = get_ram_info()
    return format_mem_info(
        available=mem.available,
        total=mem.total,
        entry_separator=entry_separator,
        sep=separator,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )


def get_formatted_swap_info(
    entry_sep: str, sep: str, entry_prefix: str, entry_suffix: str
) -> str:
    logs_infix: str = f"{entry_sep=}{s}{sep=}{s}{entry_prefix=}{s}{entry_suffix=}{s}"
    ldbg(f"{logs_infix}Getting formatted swap info")
    mem: SwapInfo = get_swap_info()
    ret: str = format_mem_info(
        available=mem.free,
        total=mem.total,
        entry_separator=entry_sep,
        sep=sep,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )
    assert isinstance(ret, str), "Return not of correct type!"
    return ret


def make_mem_entry(
    name: str, sep: str, amount_t: str, entry_prefix: str, entry_suffix: str
) -> str:
    return f"{entry_prefix}{name}{sep}{amount_t}{entry_suffix}"


def make_mem_entry_from_bytes_amount(
    name: str,
    sep: str,
    amount: int,
    amount_digits: int,
    entry_prefix: str,
    entry_suffix: str,
) -> str:
    amount_gb: float = amount / _BYTES_IN_GB
    amount_t: str = f"{amount_gb:.{amount_digits}f} GB"
    return make_mem_entry(
        name=name,
        sep=sep,
        amount_t=amount_t,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )


def format_mem_info(
    available: int,
    total: int,
    entry_separator: str,
    sep: str,
    entry_prefix: str,
    entry_suffix: str,
) -> str:
    # Not using psutil's "used" because I found it inconsistent in my testing
    used: int = total - available
    used_entry: str = make_mem_entry_from_bytes_amount(
        name="Used",
        sep=sep,
        amount=used,
        amount_digits=2,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )
    available_entry: str = make_mem_entry_from_bytes_amount(
        name="Available",
        sep=sep,
        amount=available,
        amount_digits=2,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )
    total_entry: str = make_mem_entry_from_bytes_amount(
        name="Total",
        sep=sep,
        amount=total,
        amount_digits=2,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )
    entries: list[str] = [used_entry, available_entry, total_entry]
    return entry_separator.join(entries)


# CPU =================================================

# TODO: If necessary - edit the code to use something like PercpuInfo and Collection[PercpuInfo]
# like I did in the procs section. Instead of this non-flexible system with joining stuff together


def get_formatted_percpu_info(
    sort: bool,
    use_interval: float,
    entries_sep: str,
    sep: str,
    sort_by_use: bool,
    entry_prefix: str,
    entry_suffix: str,
    sort_reverse: bool,
) -> str:
    logs_infix: str = f"{sort=}{s}{use_interval=}{s}{entries_sep=}{s}{sep=}{s}{sort_by_use=}{s}{entry_prefix=}{s}{entry_suffix=}{s}"
    ldbg(f"{logs_infix}Getting formatted percpu info")
    id_start: int = 0
    freqs: PercpuFreqs = get_percpu_freqs()
    uses: PercpuUses = get_percpu_uses(
        interval=use_interval,
    )
    sort_by_freqs: bool = not sort_by_use
    freqs_uses: PercpuFreqsUses = join_freqs_uses(freqs, uses)
    if sort:
        freqs_uses = sort_freqs_uses(
            freqs_uses=freqs_uses,
            sort_by_freqs=sort_by_freqs,
            sort_reverse=sort_reverse,
        )
    formatted: str = format_percpu_info(
        freqs_uses=freqs_uses,
        id_start=id_start,
        entries_separator=entries_sep,
        sep=sep,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )
    return formatted


def join_freqs_uses(freqs: PercpuFreqs, uses: PercpuUses) -> PercpuFreqsUses:
    freqs_d: dict[int, scpufreq] = dict(freqs)
    uses_d: dict[int, float] = dict(uses)
    if not have_same_keys(freqs_d, uses_d):
        raise RuntimeError("Frequencies and uses don't have the same keys")
    return [(id, freqs_d[id], uses_d[id]) for id in freqs_d]


def get_percpu_freqs() -> PercpuFreqs:
    return list(enumerate(psutil.cpu_freq(True)))


def get_percpu_uses(interval: float) -> PercpuUses:
    return list(enumerate(psutil.cpu_percent(percpu=True, interval=interval)))


def sort_freqs_uses(
    freqs_uses: PercpuFreqsUses, sort_by_freqs: bool, sort_reverse: bool
) -> PercpuFreqsUses:
    """If not sort_by_freqs -> will sort by use"""
    sortkey: Callable[[PercpuFreqUse], SupportsRichComparison_]
    if sort_by_freqs:
        sortkey = lambda x: x[1].current
    else:
        sortkey = lambda x: x[2]
    # Underscore is to avoid naming conflict with sorted()
    sorted_ = sorted(freqs_uses, key=sortkey, reverse=sort_reverse)
    return sorted_


def make_percpu_info_entry(
    id_t: str,
    current_t: str,
    max_t: str,
    use_t: str,
    type_: str,
    sep: str,
    entry_prefix: str,
    entry_suffix: str,
) -> str:
    return f"{entry_prefix}{type_} {id_t} ({max_t}){sep}Use: {use_t}{sep}{current_t}{entry_suffix}"


def make_percpu_current_text(current: float, decimals: int) -> str:
    current_ghz: float = current / 1000
    current_f: str = f"{current_ghz:.{decimals}f}"
    current_t: str = f"{current_f} GHz"
    return current_t


def make_percpu_use_text(use: float, decimals: int) -> str:
    use_ghz: float = use
    use_f: str = f"{use_ghz:.{decimals}f}"
    use_t: str = f"{use_f}%"
    return use_t


def make_percpu_max_text(max_: float, decimals: int) -> str:
    max_ghz: float = max_ / 1000
    max_t: str = f"{max_ghz:.{decimals}f} GHz"
    return max_t


def make_percpu_id_text(id: int, id_start: int, padding: int) -> str:
    id_f: int = id + id_start
    id_t: str = pad_left_to_length(text=str(id_f), length=padding, padding=" ")
    return id_t


def make_percpu_info_entry_from_data(
    id: int,
    id_pad_to_length: int,
    id_start: int,
    current: float,
    max_: float,
    use: float,
    is_logical: bool,
    sep: str,
    entry_prefix: str,
    entry_suffix: str,
) -> str:
    if current == 0:
        logs_infix: str = f"{id=}{s}"
        lwarn(f"{logs_infix}Current is zero!")
    if max_ == 0:
        logs_infix: str = f"{id=}{s}"
        lwarn(f"{logs_infix}Max is zero!")
    if use == 0:
        logs_infix: str = f"{id=}{s}"
        lwarn(f"{logs_infix}Use is zero!")
    current_t: str = make_percpu_current_text(
        current, CMD_HOST_STATS_CPU_ENTRY_CURRENT_DECIMALS
    )
    use_t: str = make_percpu_use_text(use, CMD_HOST_STATS_CPU_ENTRY_USE_DECIMALS)
    max_t: str = make_percpu_max_text(max_, CMD_HOST_STATS_CPU_ENTRY_MAX_DECIMALS)
    id_t: str = make_percpu_id_text(id, id_start, id_pad_to_length)
    type_: str = "Thread" if is_logical else "Core"
    return make_percpu_info_entry(
        id_t=id_t,
        current_t=current_t,
        max_t=max_t,
        use_t=use_t,
        type_=type_,
        sep=sep,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )


def format_percpu_info(
    freqs_uses: PercpuFreqsUses,
    id_start: int,
    entries_separator: str,
    sep: str,
    entry_prefix: str,
    entry_suffix: str,
) -> str:
    logical_cpus_count: int = len(freqs_uses)
    id_padding_to_length: int = math.ceil(math.log10(logical_cpus_count))

    entries: list[str] = []
    for id, freq, use in freqs_uses:
        if freq.max <= 0:
            logs_infix: str = f"{id=}{s}{freq.max=}{s}"
            lwarn(f"{logs_infix}Thread max freq is zero or lower")
        is_logical: bool = True
        entry: str = make_percpu_info_entry_from_data(
            id,
            id_padding_to_length,
            id_start,
            freq.current,
            freq.max,
            use,
            is_logical,
            sep,
            entry_prefix,
            entry_suffix,
        )
        entries.append(entry)
    return entries_separator.join(entries)


# PROCESSES =================================================




def get_proc_cpu_use(proc: psutil.Process, interval: float | None) -> float | None:
    try:
        return proc.cpu_percent(interval=interval)
    except psutil.ZombieProcess:
        ldbg("Found zombie process when retrieving process cpu usage. Skipping it")
    except psutil.NoSuchProcess:
        ldbg("Found non-existent process when retrieving cpu usage. Skipping it")
    except psutil.AccessDenied:
        ldbg("Got access denied when retrieving process cpu usage. Skipping it")
    return None


def sort_procs_cpu_uses(
    procs: Collection[ProcInfo], sort_reverse: bool
) -> Collection[ProcInfo]:
    # Requires all the procs to have a defined cpu usage
    def sortkey(x: ProcInfo) -> float:
        cpu_use: float | None = x.cpu_use
        if cpu_use is None:
            raise RuntimeError("Cpu usage of process is not defined")
        return cpu_use

    return sorted(procs, key=sortkey, reverse=sort_reverse)


def get_procs_cpu_uses_info(interval: float) -> Collection[ProcInfo]:
    procs: list[psutil.Process] = list(psutil.process_iter())
    procs_infos: list[ProcInfo] = [ProcInfo(proc) for proc in procs]
    attach_procs_cpu_uses(procs_infos, interval)
    return procs_infos


def attach_procs_cpu_uses(procs: Collection[ProcInfo], interval: float) -> None:
    # NOTE: Make sure that the procs array is NOT modified when this function is running
    # Procs that we cannot get the usage of not be included in the returned list
    for proc_info in procs:
        _ = (
            proc_info.proc.cpu_percent()
        )  # Could be replaced with get_proc_cpu_use but this is more efficient
    # An async approach was tested here but (for whatever reason) it was found to be slower than this simpler synchronous approach
    time.sleep(interval)
    uses: list[float | None] = []
    for proc_info in procs:
        use: float | None = get_proc_cpu_use(proc_info.proc, interval=None)
        if use is None:
            status: str = proc_info.proc.status() # The actual type is psutil._Status 
            pid: int = proc_info.proc.pid
            logs_infix: str = f"{status=}{s}{pid=}{s}"
            lwarn(f"{logs_infix}Couldn't get CPU usage of process")
        uses.append(use)

    assert len(procs) == len(uses), "Amount of procs and cpu usages must be equal"
    for i, proc_info in enumerate(procs):
        use: float | None = uses[i]
        if use is None:
            continue
        proc_info.cpu_use = use


# TODO
# def attach_proc_ram_use()


# def attach_procs_ram_uses(procs: Collection[ProcInfo]) -> None:
#     for procs_info in procs:


def make_proc_entry(
    proc_info: ProcInfo,
    sep: str,
    entry_prefix: str,
    entry_suffix: str,
) -> str:
    # TODO
    # proc_info: psutil.Process = proc_info[0]
    # use: float = proc_info.cpu
    # name: str = proc_info.name()
    # niceness: int = proc_info.nice()
    # pid: int = proc_info.pid
    # return f"{entry_prefix}"
    return "sussy baka"


def format_procs_infos(
    procs_infos: Collection[ProcInfo],
    entries_separator: str,
    sep: str,
    entry_prefix: str,
    entry_suffix: str,
) -> str:
    entries: list[str] = []
    for proc_use in procs_infos:
        entry: str = make_proc_entry(
            proc_info=proc_use,
            sep=sep,
            entry_prefix=entry_prefix,
            entry_suffix=entry_suffix,
        )
        entries.append(entry)
    return entries_separator.join(entries)


def limit_procs_infos(
    procs_infos: Collection[ProcInfo], limit: int | None
) -> Collection[ProcInfo]:
    if limit is None:
        return procs_infos
    if limit < 0:
        logs_infix: str = f"{limit=}{s}"
        raise RuntimeError(f"{logs_infix}Incorrect entries limit")
    # Only checks for presence of the dunder method, not its signature
    if isinstance(procs_infos, SupportsGetItem):
        return procs_infos[:limit]
    return list(procs_infos)[:limit]


def get_formatted_procs_info(
    entries_limit: int | None,
    uses_interval: float,
    entries_separator: str,
    sep: str,
    entry_prefix: str,
    entry_suffix: str,
) -> str:
    procs_infos: Collection[ProcInfo] = get_procs_cpu_uses_info(uses_interval)
    procs_infos = limit_procs_infos(procs_infos=procs_infos, limit=entries_limit)
    return format_procs_infos(
        procs_infos=procs_infos,
        entries_separator=entries_separator,
        sep=sep,
        entry_prefix=entry_prefix,
        entry_suffix=entry_suffix,
    )