import logging
import logging.handlers
import asyncio
import os
import time
from typing import Mapping, Any

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

from .ranks import RanksRegistry
from .commands import CommandsRegistry
from .ranks import RanksRegistry, owners_from_environment, trusted_from_environment
from .bot import Bot
from .networking import (
    NetworkingHandler,
    ReplyDispatcher,
    RequestReplier,
    LazySocket,
)

from .hardcoded import (
    DISCORD_REACHABILITY_INTERVAL,
    DISCORD_REACHABILITY_TRIES,
    LOGGING_MAIN_NAME,
    MODE_OPTION_SERVER,
    MODE_OPTION_CLIENT,
    LOGGING_MAIN_LEVEL,
    LOGGING_MAIN_FILE,
    LOGGING_MAIN_FORMAT,
    LOGGING_MAX_BYTES,
    LOGGING_BACKUP_COUNT,
    LOGGING_DISCORD_FORMAT,
    LOGGING_DISCORD_FILE,
    LOGGING_DISCORD_LEVEL,
    ENV_KEY_DOTENV_PATH,
    ENV_KEY_TOKEN,
    ENV_KEY_BOT_PREFIX,
    NETWORK_CHECK_DOMAIN,
    ENV_KEY_MODE,
    ENV_KEY_NETWORKING_CLIENT_CONNECT_URL,
    ENV_KEY_NETWORKING_CLIENT_BIND_URL,
    ENV_KEY_NETWORKING_CURVE_CLIENT_PUBLICKEY,
    ENV_KEY_NETWORKING_CURVE_CLIENT_SECRETKEY,
    ENV_KEY_NETWORKING_CURVE_SERVER_PUBLICKEY,
    ENV_KEY_NETWORKING_CURVE_SERVER_SECRETKEY,
    ENV_KEY_NETWORKING_SERVER_BIND_URL,
    ENV_KEY_NETWORKING_SERVER_CONNECT_URL,
    ENV_KEY_TUYA_ACCESS_ID,
    ENV_KEY_TUYA_ACCESS_SECRET,
    ENV_KEY_TUYA_REGION,
    ENV_KEY_TUYA_DEVICE_ID,
    TUYA_POWER_OFF_CMD,
    TUYA_POWER_ON_CMD,
    POWEROFF_WAIT_TIME_SECONDS,
    ENV_KEY_BOT_STATUS,
    NET_HEARTBEAT_IVL_MS,
    NET_HEARTBEAT_TIMEOUT_MS,
)
from .main_convenience import get_env_or_error
from .minecraft import (
    MinecraftContext,
)  # Must be imported in the shared global scope due to bad programming
from .networking import check_is_reachable


async def main_client() -> None:
    from .cmd_serverstart import setup_cmd_serverstart
    from .cmd_serverview import setup_cmd_serverview
    from .cmd_servercmd import setup_cmd_servercmd
    from .cmd_help import setup_cmd_help
    from .cmd_debug_sendnetrequest import setup_cmd_debug_sendnetrequest
    from .cmd_debug_setupsimplenetcodereplier import (
        setup_cmd_debug_setupsimplenetcodereplier,
    )
    from .cmd_poweroff import setup_cmd_poweroff

    from .cmd_testpowerdeviceconnectionrequest import (
        setup_cmd_testpowerdeviceconnectionrequest,
    )

    logging.info("Client main start!" + "-" * 50)

    client_bind_url: str = get_env_or_error(ENV_KEY_NETWORKING_CLIENT_BIND_URL)
    client_connect_url: str = get_env_or_error(ENV_KEY_NETWORKING_CLIENT_CONNECT_URL)
    client_curve_public_key: str = get_env_or_error(
        ENV_KEY_NETWORKING_CURVE_CLIENT_PUBLICKEY
    )
    client_curve_secret_key: str = get_env_or_error(
        ENV_KEY_NETWORKING_CURVE_CLIENT_SECRETKEY
    )
    # server_bind_url: str = get_env_or_error(ENV_KEY_NETWORKING_SERVER_BIND_URL)
    # server_connect_url: str = get_env_or_error(ENV_KEY_NETWORKING_SERVER_CONNECT_URL)
    server_curve_public_key: str = get_env_or_error(
        ENV_KEY_NETWORKING_CURVE_SERVER_PUBLICKEY
    )
    # server_curve_secret_key: str = get_env_or_error(
    #     ENV_KEY_NETWORKING_CURVE_SERVER_SECRETKEY
    # )

    zmq_context: zmq.asyncio.Context = zmq.asyncio.Context()
    reply_dispatcher: ReplyDispatcher = ReplyDispatcher()

    request_replier: RequestReplier = RequestReplier()

    sock_lazy: LazySocket = LazySocket(
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
    await sock_lazy.start()

    networking_handler: NetworkingHandler = NetworkingHandler(
        reply_dispatcher=reply_dispatcher,
        request_replier=request_replier,
        sock_lazy=sock_lazy,
    )
    await networking_handler.start()

    minecraft_context: MinecraftContext = MinecraftContext()

    ranks_registry: RanksRegistry = RanksRegistry()
    ranks_registry.add_trusted(trusted_from_environment())
    ranks_registry.add_owners(owners_from_environment())

    commands_lock: asyncio.Lock = asyncio.Lock()

    group_registry: click.Group = click.Group()
    click.pass_context(group_registry)
    commands_registry: CommandsRegistry = CommandsRegistry(
        group=group_registry,
        minecraft_context=minecraft_context,
        networking_handler=networking_handler,
        client_power_controller=None,
        commands_lock=commands_lock,
    )

    setup_cmd_test(commands_registry, ranks_registry)
    setup_cmd_testarg(commands_registry, ranks_registry)
    setup_cmd_testblocking(commands_registry, ranks_registry)
    setup_cmd_testerror(commands_registry, ranks_registry)
    setup_cmd_testpermissions(commands_registry, ranks_registry)
    setup_cmd_teststream(commands_registry, ranks_registry)

    setup_cmd_testpowerdeviceconnectionrequest(commands_registry, ranks_registry)

    setup_cmd_help(commands_registry, ranks_registry)
    setup_cmd_debug_sendnetrequest(commands_registry, ranks_registry)
    setup_cmd_debug_setupsimplenetcodereplier(commands_registry, ranks_registry)

    setup_cmd_poweroff(commands_registry, ranks_registry)
    setup_cmd_serverstart(commands_registry, ranks_registry)
    setup_cmd_servercmd(commands_registry, ranks_registry)
    setup_cmd_serverview(commands_registry, ranks_registry)

    token: str = get_env_or_error(ENV_KEY_TOKEN)
    bot_prefix: str = get_env_or_error(ENV_KEY_BOT_PREFIX)
    bot_status: str | None = get_env_or_error(ENV_KEY_BOT_STATUS)

    bot: Bot = Bot(bot_prefix, registry=commands_registry, status=bot_status)
    await bot.run(token=token)


async def main_server() -> None:
    from .cmd_help import setup_cmd_help
    from .cmd_debug_sendnetrequest import setup_cmd_debug_sendnetrequest
    from .cmd_debug_setupsimplenetcodereplier import (
        setup_cmd_debug_setupsimplenetcodereplier,
    )
    from .cmd_poweron import setup_cmd_poweron
    from .cmd_dangerous_instant_poweroff import setup_cmd_dangerous_instant_poweroff

    from .os_management import ShutdownResponder, PowerDeviceStatusResponder
    from .clientpower import TuyaPowerController, PowerController

    from .cmd_testpowerdeviceconnection import setup_cmd_testpowerdeviceconnection

    logging.info("Server main start!" + "-" * 50)

    # client_bind_url: str = get_env_or_error(ENV_KEY_NETWORKING_CLIENT_BIND_URL)
    # client_connect_url: str = get_env_or_error(ENV_KEY_NETWORKING_CLIENT_CONNECT_URL)
    client_curve_public_key: str = get_env_or_error(
        ENV_KEY_NETWORKING_CURVE_CLIENT_PUBLICKEY
    )
    # client_curve_secret_key: str = get_env_or_error(
    #     ENV_KEY_NETWORKING_CURVE_CLIENT_SECRETKEY
    # )
    server_bind_url: str = get_env_or_error(ENV_KEY_NETWORKING_SERVER_BIND_URL)
    server_connect_url: str = get_env_or_error(ENV_KEY_NETWORKING_SERVER_CONNECT_URL)
    server_curve_public_key: str = get_env_or_error(
        ENV_KEY_NETWORKING_CURVE_SERVER_PUBLICKEY
    )
    server_curve_secret_key: str = get_env_or_error(
        ENV_KEY_NETWORKING_CURVE_SERVER_SECRETKEY
    )

    tuya_access_id: str = get_env_or_error(ENV_KEY_TUYA_ACCESS_ID)
    tuya_access_secret: str = get_env_or_error(ENV_KEY_TUYA_ACCESS_SECRET)
    tuya_region: str = get_env_or_error(ENV_KEY_TUYA_REGION)
    tuya_device_id: str = get_env_or_error(ENV_KEY_TUYA_DEVICE_ID)
    tuya_power_on_command: Mapping[Any, Any] = TUYA_POWER_ON_CMD
    tuya_power_off_command: Mapping[Any, Any] = TUYA_POWER_OFF_CMD
    client_power_controller: PowerController = TuyaPowerController(
        access_id=tuya_access_id,
        access_secret=tuya_access_secret,
        region=tuya_region,
        device_id=tuya_device_id,
        power_on_command=tuya_power_on_command,
        power_off_command=tuya_power_off_command,
    )

    zmq_context: zmq.asyncio.Context = zmq.asyncio.Context()
    reply_dispatcher: ReplyDispatcher = ReplyDispatcher()
    request_replier: RequestReplier = RequestReplier()
    sock_lazy: LazySocket = LazySocket(
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
    await sock_lazy.start()
    networking_handler: NetworkingHandler = NetworkingHandler(
        reply_dispatcher=reply_dispatcher,
        request_replier=request_replier,
        sock_lazy=sock_lazy,
    )
    await networking_handler.start()

    # UNUSED!!! BUT MUST BE CREATED DUE TO SHITTY CODE
    minecraft_context: MinecraftContext = MinecraftContext()

    shutdown_responder: ShutdownResponder = ShutdownResponder(
        client_power_controller=client_power_controller,
        sleeping_time_after_request=POWEROFF_WAIT_TIME_SECONDS,
    )
    shutdown_responder.start(networking_handler=networking_handler)

    # power_device_status_responder: PowerDeviceStatusResponder = (
    #     PowerDeviceStatusResponder(client_power_controller=client_power_controller)
    # )
    # power_device_status_responder.start(networking_handler=networking_handler)

    ranks_registry: RanksRegistry = RanksRegistry()
    ranks_registry.add_trusted(trusted_from_environment())
    ranks_registry.add_owners(owners_from_environment())

    commands_lock: asyncio.Lock = asyncio.Lock()

    group_registry: click.Group = click.Group()
    click.pass_context(group_registry)
    commands_registry: CommandsRegistry = CommandsRegistry(
        group=group_registry,
        minecraft_context=minecraft_context,
        networking_handler=networking_handler,
        client_power_controller=client_power_controller,
        commands_lock=commands_lock,
    )

    setup_cmd_test(commands_registry, ranks_registry)
    setup_cmd_testarg(commands_registry, ranks_registry)
    setup_cmd_testblocking(commands_registry, ranks_registry)
    setup_cmd_testerror(commands_registry, ranks_registry)
    setup_cmd_testpermissions(commands_registry, ranks_registry)
    setup_cmd_teststream(commands_registry, ranks_registry)

    setup_cmd_testpowerdeviceconnection(commands_registry, ranks_registry)

    setup_cmd_help(commands_registry, ranks_registry)
    setup_cmd_debug_sendnetrequest(commands_registry, ranks_registry)
    setup_cmd_debug_setupsimplenetcodereplier(commands_registry, ranks_registry)

    setup_cmd_poweron(commands_registry, ranks_registry)
    setup_cmd_dangerous_instant_poweroff(commands_registry, ranks_registry)

    token: str = get_env_or_error(ENV_KEY_TOKEN)
    bot_prefix: str = get_env_or_error(ENV_KEY_BOT_PREFIX)
    bot_status: str | None = get_env_or_error(ENV_KEY_BOT_STATUS)

    bot: Bot = Bot(bot_prefix, registry=commands_registry, status=bot_status)
    await bot.run(token=token)


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
