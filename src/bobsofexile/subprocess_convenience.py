import logging
import asyncio.subprocess
import asyncio


async def terminate_and_kill_process(
    process: asyncio.subprocess.Process,
    terminate_attempts: int,
    terminate_interval: float,
    kill_bonus_delay: float,
) -> None:
    """A kill will happen  terminate_interval+kill_bonus_delay after the last term attempt."""
    for attempt in range(1, terminate_attempts + 1):
        logging.info(f"Attempting to terminate process | {process.pid=} | {attempt=}")
        process.terminate()
        try:
            async with asyncio.timeout(delay=terminate_interval):
                return_code: int = await process.wait()
        except TimeoutError:
            logging.debug("Process termination timed out, will try again")
        else:
            logging.info(f"Process termination successful | {process.pid=} | {return_code=}")
            return

    await asyncio.sleep(kill_bonus_delay)
    logging.warning(f"Killing process due to terminates exhaustion | {process.pid=}")
    process.kill()
    kill_return_code: int = await process.wait()
    logging.info(f"Process killing successful | {process.pid=} | {kill_return_code=}")

