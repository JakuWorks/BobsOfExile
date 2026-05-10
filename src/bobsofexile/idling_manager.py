import logging
import asyncio

from .cmd_poweroff import invoke_poweroff
from .commands import (
    ICommandCall,
    ICommandInvocationStandard,
    call_command_featureful,
    LockingComponentStandard,
    PermissionInfoComponentDummy,
    CallContextGrand,
)
from .minecraft import MinecraftManager
from .responder import IResponder


class IdlingManager:
    __slots__ = (
        "interval",
        "commands_lock",
        "minecraft_manager",
        "responder",
        "call_context_grand",
    )

    interval: float
    commands_lock: asyncio.Lock
    minecraft_manager: MinecraftManager | None
    responder: IResponder
    call_context_grand: CallContextGrand

    def __init__(
        self,
        interval: float,
        minecraft_manager: MinecraftManager | None,
        responder: IResponder,
        call_context_grand: CallContextGrand,
    ) -> None:
        # Representing command calling info as a tuple makes the impossible state when one is missing impossible
        # to represent. Just trying out this pattern to see how it goes
        self.minecraft_manager = minecraft_manager
        self.interval = interval
        self.responder = responder
        self.call_context_grand = call_context_grand

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

            locking_component: LockingComponentStandard = LockingComponentStandard(
                self.call_context_grand.commands_lock
            )

            if locking_component.is_locked():
                logging.info(
                    "Idling manager: cannot proceed due to taken commands lock"
                )
                continue

            logging.debug("Idling manager preparing poweroff call")
            poweroff_invocation: ICommandInvocationStandard = invoke_poweroff()
            poweroff_call: ICommandCall = poweroff_invocation.make_call(
                responder=self.responder, call_context_grand=self.call_context_grand
            )
            logging.info("Idling manager calling poweroff!")

            await self.responder.respond("Idle manager: Bot is idling; will power off")

            await call_command_featureful(
                call=poweroff_call,
                responder=self.responder,
                permissions=PermissionInfoComponentDummy(),
                lock=locking_component,
            )
