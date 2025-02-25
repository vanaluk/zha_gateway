"""Coordinator entry point."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from coordinator import Coordinator

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Reduce verbosity of some modules
    for module in ["zigpy.zcl", "zigpy.zdo", "aiosqlite"]:
        logging.getLogger(module).setLevel(logging.INFO)


async def run_coordinator(device_path: str) -> None:
    """Run the coordinator with proper error handling."""
    coordinator: Optional[Coordinator] = None
    try:
        coordinator = Coordinator(device_path)
        await coordinator.start()

        # Wait for interrupt
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received termination signal")
    except (ConnectionError, OSError) as e:
        logger.exception("Hardware or connection error: %s", e)
        raise
    except RuntimeError as e:
        logger.exception("Runtime coordinator error: %s", e)
        raise
    finally:
        if coordinator:
            try:
                await coordinator.stop()
            except (ConnectionError, OSError) as e:
                logger.error("Error during hardware shutdown: %s", e)
            except RuntimeError as e:
                logger.error("Runtime error during coordinator shutdown: %s", e)


def main() -> None:
    """Main entry point."""
    setup_logging()

    device_path = "/dev/ttyACM0"
    if not Path(device_path).exists():
        logger.error("Device %s not found", device_path)
        return

    try:
        asyncio.run(run_coordinator(device_path))
    except (KeyboardInterrupt, SystemExit):
        logger.error("Exiting coordinator")
        sys.exit(0)
    except (ConnectionError, OSError) as e:
        logger.exception("Hardware or connection error: %s", e)
        sys.exit(1)
    except RuntimeError as e:
        logger.exception("Runtime coordinator error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
