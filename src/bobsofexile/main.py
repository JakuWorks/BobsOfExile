import logging
import logging.handlers
import asyncio
import os
import time
from typing import Any
from collections.abc import Sequence, Mapping, MutableSequence

import asyncclick as click
import dotenv
import zmq.asyncio
import discord

from .cmd_test import setup_cmd_test
from .cmd_testarg import setup_cmd_testarg
from .cmd_testblocking import setup_cmd_testblocking
from .cmd_testerror import setup_cmd_testerror
from .cmd_testpermissions import setup_cmd_testpermissions
from .cmd_teststream import setup_cmd_teststream
from .cmd_testping import setup_cmd_testping

from .async_convenience import wrap_error_logging
from .ranks import RanksRegistry
from .commands import CommandsRegistry, LockingComponentDummy, LockingComponentStandard
from .permission_info import PermissionInfoDummy
from .ranks import RanksRegistry, owners_from_environment, trusted_from_environment
from .bot import Bot
from .networking_framework import (
    NetworkingHandler,
    ReplyDispatcher,
    RequestReplier,
    ILazySocket,
)
from .networking_socket import (
    LazySocket,
    IOneTimeLazySocketCloner,
    OneTimeLazySocketCloner,
)
from .ping_pong_responder import PingPongResponder

from .hardcoded import (
    DISCORD_REACHABILITY_INTERVAL,
    DISCORD_REACHABILITY_TRIES,
    ENV_KEY_BOT_PREFIX,
    ENV_KEY_BOT_STATUS,
    ENV_KEY_DOTENV_PATH,
    ENV_KEY_MINECRAFT_RAM_COUNTING_ENABLE,
    ENV_KEY_MINECRAFT_RAM_MAX_USAGE_MB,
    ENV_KEY_MINECRAFT_COMMANDS_DEFAULT_TARGET,
    ENV_KEY_MINECRAFT_EMPTY_CHECK_INTERVAL_S,
    ENV_KEY_MODE,
    ENV_KEY_NETWORKING_CLIENT_BIND_URL,
    ENV_KEY_NETWORKING_CLIENT_CONNECT_URL,
    ENV_KEY_NETWORKING_CURVE_CLIENT_PUBLICKEY,
    ENV_KEY_NETWORKING_CURVE_CLIENT_SECRETKEY,
    ENV_KEY_NETWORKING_CURVE_SERVER_PUBLICKEY,
    ENV_KEY_NETWORKING_CURVE_SERVER_SECRETKEY,
    ENV_KEY_NETWORKING_SERVER_BIND_URL,
    ENV_KEY_NETWORKING_SERVER_CONNECT_URL,
    ENV_KEY_TOKEN,
    ENV_KEY_TUYA_ACCESS_ID,
    ENV_KEY_TUYA_ACCESS_SECRET,
    ENV_KEY_TUYA_DEVICE_ID,
    ENV_KEY_IDLING_MANAGER_ENABLE,
    ENV_KEY_IDLING_MANAGER_INTERVAL_SECONDS,
    ENV_KEY_TUYA_REGION,
    LOGGING_BACKUP_COUNT,
    LOGGING_DISCORD_FILE,
    LOGGING_DISCORD_FORMAT,
    LOGGING_DISCORD_LEVEL,
    LOGGING_MAIN_FILE,
    LOGGING_MAIN_FORMAT,
    LOGGING_MAIN_LEVEL,
    LOGGING_MAIN_NAME,
    LOGGING_MAX_BYTES,
    MODE_OPTION_CLIENT,
    MODE_OPTION_SERVER,
    NETWORK_CHECK_DOMAIN,
    NET_HEARTBEAT_IVL_MS,
    NET_HEARTBEAT_TIMEOUT_MS,
    POWEROFF_WAIT_TIME_SECONDS,
    TUYA_POWER_OFF_CMD,
    TUYA_POWER_ON_CMD,
)
from .main_convenience import (
    get_env_or_error,
    get_env_or_error_float_positive,
    get_env_or_error_bool,
    get_env_or_error_int_positive,
)
from .net_convenience import check_is_reachable


async def main_client() -> None:
    from .minecraft import (
        MinecraftManager,
        MinecraftEntryConfigFromEnv,
        MinecraftInstanceEntry,
        MinecraftEntryStartPreconfiguration,
        new_minecraft_entry_from_env_config,
        new_minecraft_entry_start_preconfiguration_from_env_config,
    )
    from .minecraft_convenience import collect_minecraft_entry_configs_from_env
    from .minecraft_ram import (
        MinecraftRamCounterStandard,
        MinecraftRamCounterDummy,
        IMinecraftRamCounter,
    )
    from .idling_manager import IdlingManager
    from .discord_responder import get_default_responder_from_config, IResponder

    from .cmd_serverstart import setup_cmd_serverstart
    from .cmd_serverview import setup_cmd_serverview
    from .cmd_servercmd import setup_cmd_servercmd
    from .cmd_serverstop import setup_cmd_serverstop
    from .cmd_serverstatus import setup_cmd_serverstatus
    from .cmd_help import setup_cmd_help
    from .cmd_debug_sendnetrequest import setup_cmd_debug_sendnetrequest
    from .cmd_debug_setupsimplenetcodereplier import (
        setup_cmd_debug_setupsimplenetcodereplier,
    )
    from .cmd_poweroff import setup_cmd_poweroff, CommandCallerPoweroff

    from .cmd_testpowerdeviceconnectionrequest import (
        setup_cmd_testpowerdeviceconnectionrequest,
    )

    logging.info("Client main start!" + "-" * 50)

    # fmt: off
    client_bind_url: str = get_env_or_error(ENV_KEY_NETWORKING_CLIENT_BIND_URL)
    client_connect_url: str = get_env_or_error(ENV_KEY_NETWORKING_CLIENT_CONNECT_URL)
    client_curve_public_key: str = get_env_or_error(ENV_KEY_NETWORKING_CURVE_CLIENT_PUBLICKEY)
    client_curve_secret_key: str = get_env_or_error(ENV_KEY_NETWORKING_CURVE_CLIENT_SECRETKEY)
    server_curve_public_key: str = get_env_or_error(ENV_KEY_NETWORKING_CURVE_SERVER_PUBLICKEY)
    minecraft_ram_counting_enable: bool = get_env_or_error_bool(ENV_KEY_MINECRAFT_RAM_COUNTING_ENABLE)
    minecraft_empty_check_interval_s: float = get_env_or_error_float_positive(ENV_KEY_MINECRAFT_EMPTY_CHECK_INTERVAL_S)
    minecraft_ram_max_usage_mb: int = get_env_or_error_int_positive(ENV_KEY_MINECRAFT_RAM_MAX_USAGE_MB)
    minecraft_commands_default_target: str = get_env_or_error(ENV_KEY_MINECRAFT_COMMANDS_DEFAULT_TARGET)
    idling_manager_enable: bool = get_env_or_error_bool(ENV_KEY_IDLING_MANAGER_ENABLE)
    idling_manager_interval_seconds: float = get_env_or_error_float_positive(ENV_KEY_IDLING_MANAGER_INTERVAL_SECONDS)
    # fmt: on

    # Keeping references of tasks created directly in main (so they don't get GCd)
    tasks_in_main: MutableSequence[asyncio.Task[None]] = []

    zmq_context: zmq.asyncio.Context = zmq.asyncio.Context()
    reply_dispatcher: ReplyDispatcher = ReplyDispatcher()

    request_replier: RequestReplier = RequestReplier()

    one_time_lazy_sock_cloner: IOneTimeLazySocketCloner = OneTimeLazySocketCloner(
        zmq_context=zmq_context,
        heartbeat_ivl=NET_HEARTBEAT_IVL_MS,
        heartbeat_timeout=NET_HEARTBEAT_TIMEOUT_MS,
        curve_key_secret=client_curve_secret_key,
        curve_key_public=client_curve_public_key,
        curve_key_server=server_curve_public_key,
        is_curve_server_role=False,
        listening_url=client_bind_url,
        requesting_and_replying_url=client_connect_url,
    )
    sock_lazy: ILazySocket = LazySocket(cloner=one_time_lazy_sock_cloner)
    sock_lazy.start()

    networking_handler: NetworkingHandler = NetworkingHandler(
        reply_dispatcher=reply_dispatcher,
        request_replier=request_replier,
        sock_lazy=sock_lazy,
    )

    tasks_in_main.append(
        asyncio.create_task(
            wrap_error_logging(
                networking_handler.start(),
                on_error_msg="Networking handler finished with an error",
            )
        )
    )

    ping_pong_responder: PingPongResponder = PingPongResponder(
        networking_handler=networking_handler
    )
    ping_pong_responder.start()

    minecraft_ram_counter: IMinecraftRamCounter
    if minecraft_ram_counting_enable:
        bytes_in_mb: int = 1048576
        minecraft_ram_counter = MinecraftRamCounterStandard(
            max_bytes=minecraft_ram_max_usage_mb * bytes_in_mb
        )
    else:
        minecraft_ram_counter = MinecraftRamCounterDummy()

    minecraft_manager: MinecraftManager = MinecraftManager(
        ram_counter=minecraft_ram_counter,
        empty_check_interval_s=minecraft_empty_check_interval_s,
    )
    tasks_in_main.append(
        asyncio.create_task(
            wrap_error_logging(
                minecraft_manager.start(),
                on_error_msg="Minecraft manager emptiness monitor finished with an error",
            )
        )
    )

    minecraft_env_configs: Sequence[MinecraftEntryConfigFromEnv] = (
        collect_minecraft_entry_configs_from_env()
    )
    for minecraft_env_config in minecraft_env_configs:
        entry: MinecraftInstanceEntry = new_minecraft_entry_from_env_config(
            minecraft_env_config
        )
        start_preconfiguration: MinecraftEntryStartPreconfiguration = (
            new_minecraft_entry_start_preconfiguration_from_env_config(
                minecraft_env_config
            )
        )
        minecraft_manager.register(entry)
        minecraft_manager.register_entry_start_preconfiguration(
            name=entry.name, preconfiguration=start_preconfiguration
        )

    ranks_registry: RanksRegistry = RanksRegistry()
    ranks_registry.add_trusted(trusted_from_environment())
    ranks_registry.add_owners(owners_from_environment())

    commands_lock_main: asyncio.Lock = asyncio.Lock()
    locking_component_main: LockingComponentStandard = LockingComponentStandard(
        commands_lock_main
    )
    locking_component_dummy: LockingComponentDummy = LockingComponentDummy()

    group_registry: click.Group = click.Group()
    click.pass_context(group_registry)

    commands_registry: CommandsRegistry = CommandsRegistry(group=group_registry)

    # fmt: off
    setup_cmd_test(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testarg(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testblocking(locking_component=locking_component_main, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testerror(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testpermissions(locking_component=locking_component_dummy, permission_info=ranks_registry.get_no_one_permission_info(), commands_registry=commands_registry)
    setup_cmd_teststream(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testping(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry, networking_handler=networking_handler)

    setup_cmd_testpowerdeviceconnectionrequest(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry, networking_handler=networking_handler)

    setup_cmd_debug_sendnetrequest(locking_component=locking_component_dummy, permission_info=ranks_registry.get_owner_permission_info(), commands_registry=commands_registry, networking_handler=networking_handler)
    setup_cmd_debug_setupsimplenetcodereplier(locking_component=locking_component_dummy, permission_info=ranks_registry.get_owner_permission_info(), commands_registry=commands_registry, networking_handler=networking_handler)

    setup_cmd_help(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)

    setup_cmd_poweroff(locking_component=locking_component_main, permission_info=ranks_registry.get_trusted_permission_info(), commands_registry=commands_registry, minecraft_manager=minecraft_manager, networking_handler=networking_handler)
    
    setup_cmd_serverstart(locking_component=locking_component_main, permission_info=ranks_registry.get_trusted_permission_info(), commands_registry=commands_registry, default_target=minecraft_commands_default_target, minecraft_manager=minecraft_manager)
    setup_cmd_serverstop(locking_component=locking_component_main, permission_info=ranks_registry.get_trusted_permission_info(), commands_registry=commands_registry, default_target=minecraft_commands_default_target, minecraft_manager=minecraft_manager)
    setup_cmd_servercmd(locking_component=locking_component_main, permission_info=ranks_registry.get_trusted_permission_info(), commands_registry=commands_registry, default_target=minecraft_commands_default_target, minecraft_manager=minecraft_manager)
    setup_cmd_serverview(locking_component=locking_component_dummy, permission_info=ranks_registry.get_trusted_permission_info(), commands_registry=commands_registry, default_target=minecraft_commands_default_target, minecraft_manager=minecraft_manager)
    setup_cmd_serverstatus(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry, minecraft_manager=minecraft_manager)
    # fmt: on

    token: str = get_env_or_error(ENV_KEY_TOKEN)
    bot_prefix: str = get_env_or_error(ENV_KEY_BOT_PREFIX)
    bot_status: str | None = get_env_or_error(ENV_KEY_BOT_STATUS)

    bot: Bot = Bot(prefix=bot_prefix, registry=commands_registry, status=bot_status)
    bot.setup_events()
    logging.info("Bot logging in")
    await bot.login(token=token)
    logging.info("Bot connecting")
    bot_task: asyncio.Task[None] = asyncio.create_task(bot.connect())
    logging.info("Waiting for bot ready")
    await bot.get_ready_event().wait()
    logging.info("Bot ready")

    if idling_manager_enable:
        default_discord_responder: IResponder = get_default_responder_from_config(
            client=bot.client
        )

        idling_manager_poweroff_caller: CommandCallerPoweroff = CommandCallerPoweroff(
            locking_component=locking_component_main,
            permission_info=PermissionInfoDummy(),
            minecraft_manager=minecraft_manager,
            networking_handler=networking_handler,
        )

        idling_manager: IdlingManager = IdlingManager(
            interval=idling_manager_interval_seconds,
            minecraft_manager=minecraft_manager,
            responder=default_discord_responder,
            poweroff_caller=idling_manager_poweroff_caller,
        )
        tasks_in_main.append(asyncio.create_task(idling_manager.start()))

    await bot_task


async def main_server() -> None:
    import tinytuya  # pyright: ignore[reportMissingTypeStubs]

    from .cmd_help import setup_cmd_help
    from .cmd_debug_sendnetrequest import setup_cmd_debug_sendnetrequest
    from .cmd_debug_setupsimplenetcodereplier import (
        setup_cmd_debug_setupsimplenetcodereplier,
    )
    from .cmd_poweron import setup_cmd_poweron
    from .cmd_powerstatus import setup_cmd_powerstatus
    from .cmd_dangerous_instant_poweroff import setup_cmd_dangerous_instant_poweroff

    from .os_management import ShutdownResponder, PowerDeviceStatusResponder
    from .power_device import IPowerController
    from .power_device_tinytuya import TuyaPowerController

    from .cmd_testpowerdeviceconnection import setup_cmd_testpowerdeviceconnection

    logging.info("Server main start!" + "-" * 50)

    # fmt: off
    client_curve_public_key: str = get_env_or_error(ENV_KEY_NETWORKING_CURVE_CLIENT_PUBLICKEY)
    server_bind_url: str = get_env_or_error(ENV_KEY_NETWORKING_SERVER_BIND_URL)
    server_connect_url: str = get_env_or_error(ENV_KEY_NETWORKING_SERVER_CONNECT_URL)
    server_curve_public_key: str = get_env_or_error(ENV_KEY_NETWORKING_CURVE_SERVER_PUBLICKEY)
    server_curve_secret_key: str = get_env_or_error(ENV_KEY_NETWORKING_CURVE_SERVER_SECRETKEY)

    tuya_access_id: str = get_env_or_error(ENV_KEY_TUYA_ACCESS_ID)
    tuya_access_secret: str = get_env_or_error(ENV_KEY_TUYA_ACCESS_SECRET)
    tuya_region: str = get_env_or_error(ENV_KEY_TUYA_REGION)
    tuya_device_id: str = get_env_or_error(ENV_KEY_TUYA_DEVICE_ID)
    # fmt: on

    # Keeping references of tasks created directly in main (so they don't get GCd)
    tasks_in_main: MutableSequence[asyncio.Task[None]] = []

    tuya_power_on_command: Mapping[Any, Any] = TUYA_POWER_ON_CMD
    tuya_power_off_command: Mapping[Any, Any] = TUYA_POWER_OFF_CMD

    tuya_cloud: tinytuya.Cloud = tinytuya.Cloud(
        apiRegion=tuya_region, apiKey=tuya_access_id, apiSecret=tuya_access_secret
    )
    client_power_controller: IPowerController = TuyaPowerController(
        cloud=tuya_cloud,
        device_id=tuya_device_id,
        power_on_command=tuya_power_on_command,
        power_off_command=tuya_power_off_command,
    )

    zmq_context: zmq.asyncio.Context = zmq.asyncio.Context()
    reply_dispatcher: ReplyDispatcher = ReplyDispatcher()
    request_replier: RequestReplier = RequestReplier()

    one_time_lazy_sock_cloner: IOneTimeLazySocketCloner = OneTimeLazySocketCloner(
        zmq_context=zmq_context,
        listening_url=server_bind_url,
        requesting_and_replying_url=server_connect_url,
        curve_key_secret=server_curve_secret_key,
        curve_key_public=server_curve_public_key,
        curve_key_server=client_curve_public_key,
        is_curve_server_role=True,
        heartbeat_ivl=NET_HEARTBEAT_IVL_MS,
        heartbeat_timeout=NET_HEARTBEAT_TIMEOUT_MS,
    )
    sock_lazy: ILazySocket = LazySocket(cloner=one_time_lazy_sock_cloner)
    sock_lazy.start()

    networking_handler: NetworkingHandler = NetworkingHandler(
        reply_dispatcher=reply_dispatcher,
        request_replier=request_replier,
        sock_lazy=sock_lazy,
    )
    tasks_in_main.append(
        asyncio.create_task(
            wrap_error_logging(
                networking_handler.start(),
                on_error_msg="Networking handler finished with an error",
            )
        )
    )

    ping_pong_responder: PingPongResponder = PingPongResponder(
        networking_handler=networking_handler
    )
    ping_pong_responder.start()

    shutdown_responder: ShutdownResponder = ShutdownResponder(
        networking_handler=networking_handler,
        client_power_controller=client_power_controller,
        sleeping_time_after_request=POWEROFF_WAIT_TIME_SECONDS,
    )
    shutdown_responder.start(networking_handler=networking_handler)

    power_device_status_responder: PowerDeviceStatusResponder = (
        PowerDeviceStatusResponder(
            networking_handler=networking_handler,
            client_power_controller=client_power_controller,
        )
    )
    power_device_status_responder.start(networking_handler=networking_handler)

    ranks_registry: RanksRegistry = RanksRegistry()
    ranks_registry.add_trusted(trusted_from_environment())
    ranks_registry.add_owners(owners_from_environment())

    commands_lock_main: asyncio.Lock = asyncio.Lock()
    locking_component_main: LockingComponentStandard = LockingComponentStandard(
        commands_lock_main
    )
    locking_component_dummy: LockingComponentDummy = LockingComponentDummy()

    group_registry: click.Group = click.Group()

    commands_registry: CommandsRegistry = CommandsRegistry(group=group_registry)

    # fmt: off
    setup_cmd_test(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testarg(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testblocking(locking_component=locking_component_main, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testerror(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testpermissions(locking_component=locking_component_dummy, permission_info=ranks_registry.get_no_one_permission_info(), commands_registry=commands_registry)
    setup_cmd_teststream(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_testping(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry, networking_handler=networking_handler)

    setup_cmd_testpowerdeviceconnection(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry, client_power_controller=client_power_controller)

    setup_cmd_help(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry)
    setup_cmd_debug_sendnetrequest(locking_component=locking_component_dummy, permission_info=ranks_registry.get_owner_permission_info(), commands_registry=commands_registry, networking_handler=networking_handler)
    setup_cmd_debug_setupsimplenetcodereplier(locking_component=locking_component_dummy, permission_info=ranks_registry.get_owner_permission_info(), commands_registry=commands_registry, networking_handler=networking_handler)

    setup_cmd_poweron(locking_component=locking_component_main, permission_info=ranks_registry.get_trusted_permission_info(), commands_registry=commands_registry, client_power_controller=client_power_controller)
    setup_cmd_powerstatus(locking_component=locking_component_dummy, permission_info=ranks_registry.get_everyone_permission_info(), commands_registry=commands_registry, client_power_controller=client_power_controller)

    setup_cmd_dangerous_instant_poweroff(locking_component=locking_component_main, permission_info=ranks_registry.get_trusted_permission_info(), commands_registry=commands_registry, client_power_controller=client_power_controller, networking_handler=networking_handler)
    # fmt: on

    token: str = get_env_or_error(ENV_KEY_TOKEN)
    bot_prefix: str = get_env_or_error(ENV_KEY_BOT_PREFIX)
    bot_status: str | None = get_env_or_error(ENV_KEY_BOT_STATUS)

    bot: Bot = Bot(prefix=bot_prefix, registry=commands_registry, status=bot_status)
    bot.setup_events()
    logging.info("Bot logging in")
    await bot.login(token=token)
    logging.info("Bot connecting")
    bot_task: asyncio.Task[None] = asyncio.create_task(bot.connect())
    logging.info("Waiting for bot ready")
    await bot.get_ready_event().wait()
    logging.info("Bot ready")

    await bot_task


async def async_main() -> None:

    mode: str = get_env_or_error(ENV_KEY_MODE)
    if mode == MODE_OPTION_SERVER:
        await main_server()
    elif mode == MODE_OPTION_CLIENT:
        await main_client()
    else:
        raise SystemExit(
            f"The mode environment variable is incorrect. It can only be {MODE_OPTION_CLIENT=} or {MODE_OPTION_SERVER=}"
        )


def main() -> None:
    dotenv_path: str | None = os.getenv(ENV_KEY_DOTENV_PATH)
    if dotenv_path is None:
        dotenv_path = dotenv.find_dotenv()
        logging.info(f"Dotenv file search result {dotenv_path=}")
    else:
        logging.info(f"Using dotenv from environment variable {dotenv_path=}")
    if dotenv_path == "":
        logging.warning(
            f"Could not find a dotenv file. The program will likely exit unless the environment was set up manually in the shell. {ENV_KEY_DOTENV_PATH=}"
        )
    else:
        dotenv.load_dotenv(dotenv_path)

    for handler in logging.root.handlers:
        handler.close()
    logging.root.handlers.clear()

    main_logging_handler: logging.Handler = logging.handlers.RotatingFileHandler(
        filename=LOGGING_MAIN_FILE,
        encoding="utf-8",
        mode="a",
        backupCount=LOGGING_BACKUP_COUNT,
        maxBytes=LOGGING_MAX_BYTES,
    )
    main_logging_formatter: logging.Formatter = logging.Formatter(
        fmt=LOGGING_MAIN_FORMAT
    )
    main_logging_handler.setFormatter(main_logging_formatter)
    logging.root.setLevel(LOGGING_MAIN_LEVEL)
    logging.root.addHandler(main_logging_handler)

    logging.getLogger(LOGGING_MAIN_NAME)
    discord_library_name: str = discord.__name__.partition(".")[0]
    discord_logging_logger: logging.Logger = logging.getLogger(discord_library_name)
    discord_logging_logger.propagate = False
    discord_logging_handler: logging.Handler = logging.handlers.RotatingFileHandler(
        filename=LOGGING_DISCORD_FILE,
        encoding="utf-8",
        mode="a",
        backupCount=LOGGING_BACKUP_COUNT,
        maxBytes=LOGGING_MAX_BYTES,
    )
    discord_logging_handler.set_name(discord_library_name)
    discord_logging_handler.setLevel(LOGGING_DISCORD_LEVEL)
    discord_logging_logger.setLevel(LOGGING_DISCORD_LEVEL)
    discord_logging_formatter: logging.Formatter = logging.Formatter(
        fmt=LOGGING_DISCORD_FORMAT
    )
    discord_logging_handler.setFormatter(discord_logging_formatter)
    discord_logging_logger.addHandler(discord_logging_handler)

    # Blocking
    discord_reachable: bool = False
    for i in range(DISCORD_REACHABILITY_TRIES):
        logging.info(f"Checking discord reachability {i}")
        discord_reachable = check_is_reachable("discord.com")
        if discord_reachable:
            logging.info("Discord is reachable")
            break
        time.sleep(DISCORD_REACHABILITY_INTERVAL)
    if not discord_reachable:
        logging.error("Discord is not reachable")
        raise SystemExit(
            f"{NETWORK_CHECK_DOMAIN} is not reachable, the program must exit."
        )

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
