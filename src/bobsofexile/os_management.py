import subprocess
import asyncio
from typing import AsyncIterator
import logging

from .hardcoded import (
    NETCODE_REQUEST_POWEROFF_SOON,
    NETCODE_REPLY_POWEROFF_SOON_OK,
    POWEROFF_MOCK,
    NETCODE_REPLY_POWEROFF_SOON_NO,
    POWEROFF_CMD,
    REMOTE_POWEROFF_RETRY_INTERVAL,
    REMOTE_POWEROFF_RETRIES,
    NETCODE_REQUEST_POWER_DEVICE_STATUS,
    NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
    NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
)
from .networking_framework import (
    RequestReplyContext,
    NetworkingMessage,
    NetworkingHandler,
)
from .power_device import IPowerController, PowerDeviceConnectedResponse


def graceful_shutdown_linux() -> None:
    logging.info("Performing a graceful shutdown (linux)")
    # This commands requires root or changing permissions
    if POWEROFF_MOCK:
        return
    subprocess.run(POWEROFF_CMD)


class ShutdownResponder:
    """Meant for the server to act upon the client's requests"""

    __slots__ = (
        "sleeping_time_after_request",
        "networking_handler",
        "client_power_controller",
    )

    sleeping_time_after_request: float
    networking_handler: NetworkingHandler
    client_power_controller: IPowerController

    def __init__(
        self,
        sleeping_time_after_request: float,
        networking_handler: NetworkingHandler,
        client_power_controller: IPowerController,
    ) -> None:
        self.sleeping_time_after_request = sleeping_time_after_request
        self.networking_handler = networking_handler
        self.client_power_controller = client_power_controller

    def start(self, networking_handler: NetworkingHandler) -> None:
        # TODO Ensure starting is only done once (possibly via a convenience base class?)
        logging.info("Adding client shutdown responder hook")
        networking_handler.request_replier.add_hook(
            code=NETCODE_REQUEST_POWEROFF_SOON,
            hook=self.shutdown_reply_hook,
            once=False,
        )

    async def shutdown_reply_hook(self, ctx: RequestReplyContext) -> None:
        logging.info("Running reply hook for client shutdown request")
        msg_no: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_POWEROFF_SOON_NO,
            id=ctx.msg.id,
            is_reply=True,
            expiration=ctx.msg.expiration,
        )
        msg_ok: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_POWEROFF_SOON_OK,
            id=ctx.msg.id,
            is_reply=True,
            expiration=ctx.msg.expiration,
        )

        connected: PowerDeviceConnectedResponse | None = (
            await self.client_power_controller.get_connected()
        )
        if connected is None or not connected.connected:
            logging.info("No client shutdown due to failed device test")
            await self.networking_handler.reply(msg_no)
            return

        logging.info("Yes client shutdown soon (device test successful)")
        await self.networking_handler.reply(msg_ok)

        logging.info(f"Sleeping for {self.sleeping_time_after_request} before client shutdown") # fmt: skip
        await asyncio.sleep(self.sleeping_time_after_request)

        logging.info("Shutting down client (unless there's a failure)")
        shutdown_retrier: AsyncIterator[bool] = (
            self.client_power_controller.power_off_async_with_retries(
                retries=REMOTE_POWEROFF_RETRIES, interval=REMOTE_POWEROFF_RETRY_INTERVAL
            )
        )
        async for success in shutdown_retrier:
            logging.info(f"Shutdown attempt of client (local) {success=}")


class PowerDeviceStatusResponder:
    __slots__ = (
        "networking_handler",
        "client_power_controller",
    )

    networking_handler: NetworkingHandler
    client_power_controller: IPowerController

    def __init__(
        self,
        networking_handler: NetworkingHandler,
        client_power_controller: IPowerController,
    ) -> None:
        self.networking_handler = networking_handler
        self.client_power_controller = client_power_controller

    def start(self, networking_handler: NetworkingHandler) -> None:
        # TODO Ensure starting is only done once (possibly via a convenience base class?)
        logging.info("Adding power device status responder hook")
        networking_handler.request_replier.add_hook(
            code=NETCODE_REQUEST_POWER_DEVICE_STATUS,
            hook=self.power_device_status_hook,
            once=False,
        )

    async def power_device_status_hook(self, ctx: RequestReplyContext) -> None:
        logging.info("Running reply hook for power device status request")
        msg_no: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
            id=ctx.msg.id,
            is_reply=True,
            expiration=ctx.msg.expiration,
        )
        msg_ok: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
            id=ctx.msg.id,
            is_reply=True,
            expiration=ctx.msg.expiration,
        )

        connected: PowerDeviceConnectedResponse | None = (
            await self.client_power_controller.get_connected()
        )
        if connected is not None and connected.connected:
            logging.info("Replying client power device OK")
            await self.networking_handler.reply(msg_ok)
        else:
            logging.info("Replying client power device NO")
            await self.networking_handler.reply(msg_no)
