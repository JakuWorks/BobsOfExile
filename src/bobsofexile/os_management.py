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
    POWEROFF_RETRY_INTERVAL,
    POWEROFF_RETRIES,
    NETCODE_REQUEST_POWER_DEVICE_STATUS,
    NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
    NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
)
from .networking import (
    RequestReplyContext,
    NetworkingMessage,
    NetworkingHandler,
    RequestReplyContextYoung,
)
from .power_device import PowerController, PowerDeviceConnectedResponse


def graceful_shutdown_linux() -> None:
    logging.info("Performing a graceful shutdown (linux)")
    # This commands requires root or changing permissions
    if POWEROFF_MOCK:
        return
    subprocess.run(POWEROFF_CMD)


class ShutdownResponder:
    __slots__ = ("sleeping_time_after_request", "client_power_controller")

    sleeping_time_after_request: int | float
    client_power_controller: PowerController

    def __init__(
        self,
        sleeping_time_after_request: int | float,
        client_power_controller: PowerController,
    ) -> None:
        self.sleeping_time_after_request = sleeping_time_after_request
        self.client_power_controller = client_power_controller

    def start(self, networking_handler: NetworkingHandler) -> None:
        logging.info("Adding client shutdown responder hook")
        networking_handler.request_replier.add_hook(
            code=NETCODE_REQUEST_POWEROFF_SOON,
            hook=self.shutdown_reply_hook,
            once=False,
            ctx=RequestReplyContextYoung(networking_handler=networking_handler),
        )

    async def shutdown_reply_hook(self, ctx: RequestReplyContext) -> None:
        logging.info("Running reply hook for client shutdown request")
        msg_no: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_POWEROFF_SOON_NO,
            id=ctx.youngest.msg.id,
            is_reply=True,
            expiration=ctx.youngest.msg.expiration
        )
        msg_ok: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_POWEROFF_SOON_OK,
            id=ctx.youngest.msg.id,
            is_reply=True,
            expiration=ctx.youngest.msg.expiration
        )

        connected: PowerDeviceConnectedResponse | None = await self.client_power_controller.get_connected()
        if connected is None or not connected.connected:
            logging.info("No client shutdown due to failed device test")
            await ctx.young.networking_handler.reply(msg_no)
            return

        logging.info("Yes client shutdown soon (device test successful)")
        await ctx.young.networking_handler.reply(msg_ok)

        logging.info(
            f"Sleeping for {self.sleeping_time_after_request} before client shutdown"
        )
        await asyncio.sleep(self.sleeping_time_after_request)

        logging.info("Shutting down client (unless there's a failure)")
        shutdown_retrier: AsyncIterator[bool] = (
            self.client_power_controller.power_off_async_with_retries(
                retries=POWEROFF_RETRIES, interval=POWEROFF_RETRY_INTERVAL
            )
        )
        try:
            async for success in shutdown_retrier:
                logging.info(f"Shutdown attempt of client (local) {success=}")
        except StopAsyncIteration:
            pass


class PowerDeviceStatusResponder:
    __slots__ = ("client_power_controller",)

    client_power_controller: PowerController

    def __init__(self, client_power_controller: PowerController) -> None:
        self.client_power_controller = client_power_controller

    def start(self, networking_handler: NetworkingHandler) -> None:
        logging.info("Adding power device status responder hook")
        networking_handler.request_replier.add_hook(
            code=NETCODE_REQUEST_POWER_DEVICE_STATUS,
            hook=self.power_device_status_hook,
            once=False,
            ctx=RequestReplyContextYoung(networking_handler=networking_handler),
        )

    async def power_device_status_hook(self, ctx: RequestReplyContext) -> None:
        logging.info("Running reply hook for power device status request")
        msg_no: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
            id=ctx.youngest.msg.id,
            is_reply=True,
            expiration=ctx.youngest.msg.expiration
        )
        msg_ok: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
            id=ctx.youngest.msg.id,
            is_reply=True,
            expiration=ctx.youngest.msg.expiration
        )

        connected: PowerDeviceConnectedResponse | None = await self.client_power_controller.get_connected()
        if connected is not None and connected.connected:
            logging.info("Replying client power device OK")
            await ctx.young.networking_handler.reply(msg_ok)
        else:
            logging.info("Replying client power device NO")
            await ctx.young.networking_handler.reply(msg_no)
