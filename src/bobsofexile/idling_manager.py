import logging
import asyncio

from .cmd_poweroff import (
    CommandCallerPoweroff,
    CommandCallPoweroff,
    CommandInvocationPoweroff,
)
from .commands import (
    call_command_featureful,
    PermissionComponentDummy,
)
from .minecraft import MinecraftManager
from .responder import IResponder


class IdlingManager:
    __slots__ = ("interval", "minecraft_manager", "responder", "poweroff_caller")

    interval: float
    minecraft_manager: MinecraftManager | None
    responder: IResponder
    poweroff_caller: CommandCallerPoweroff

    def __init__(
        self,
        interval: float,
        minecraft_manager: MinecraftManager | None,
        responder: IResponder,
        poweroff_caller: CommandCallerPoweroff,
    ) -> None:
        # Representing command calling info as a tuple makes the impossible state when one is missing impossible
        # to represent. Just trying out this pattern to see how it goes
        self.interval = interval
        self.minecraft_manager = minecraft_manager
        self.responder = responder
        self.poweroff_caller = poweroff_caller

    async def start(self) -> None:
        logging.info("Starting idling manager")
        while True:
            await asyncio.sleep(self.interval)

            if self.minecraft_manager is not None:
                running_entries_count: int = len(
                    self.minecraft_manager.get_running_entries()
                )
                if running_entries_count != 0:
                    continue
                logging.info("Idling manager: no minecraft entry is running")

            logging.debug("Idling manager preparing poweroff call")
            poweroff_invocation: CommandInvocationPoweroff
            _, poweroff_invocation = self.poweroff_caller.make_invocation()
            poweroff_call: CommandCallPoweroff = self.poweroff_caller.make_call(
                invocation=poweroff_invocation, responder=self.responder
            )

            msg_poweroff: str = (
                "Bot is idling; will power off *(unless commands lock is taken)*"
            )
            logging.info(msg_poweroff)
            await self.responder.respond(msg_poweroff)
            _ = await call_command_featureful(
                call=poweroff_call,
                responder=self.responder,
                permissions=PermissionComponentDummy(),
                lock=poweroff_call.get_locking_component(),
            )
            # We don't return here in case the poweroff command fails
            # Instead the poweroff will be attempted next time
            # (Additionally calling the commands waits for it to finish so poweroffs won't be running concurrently (and a properly configured lock would protect from that as well))
