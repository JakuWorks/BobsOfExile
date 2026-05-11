import logging
import asyncio
import os
import signal

import asyncio.subprocess


async def terminate_and_kill_process_group_and_wait_for_process(
    process: asyncio.subprocess.Process,
    terminate_attempts: int,
    terminate_interval: float,
    kill_bonus_delay: float,
) -> None:
    """
    Acts upon the process group of the process
    Will fail and wait forever if the process exits the process group
    """
    for attempt in range(1, terminate_attempts + 1):
        logging.info(f"Attempting to terminate process | {process.pid=} | {attempt=}")
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        # process.terminate()
        try:
            async with asyncio.timeout(terminate_interval):
                return_code: int = await process.wait()
        except TimeoutError:
            logging.debug("Process termination timed out, will try again")
        else:
            logging.info(
                f"Process termination successful | {process.pid=} | {return_code=}"
            )
            return

    await asyncio.sleep(kill_bonus_delay)
    logging.warning(f"Killing process due to terminates exhaustion | {process.pid=}")
    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    # process.kill()
    kill_return_code: int = await process.wait()
    logging.info(f"Process killing successful | {process.pid=} | {kill_return_code=}")
