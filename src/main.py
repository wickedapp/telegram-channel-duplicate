#!/usr/bin/env python3
"""
Telegram Channel Duplicator

Monitors source channels and copies messages to a target channel
with configurable text replacements and filtering.
"""

import asyncio
import signal
import sys
import logging

from .config import Config
from .duplicator import ChannelDuplicator

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    try:
        # Load configuration
        config = Config()
        logger.info("Configuration loaded successfully")

        # Create duplicator
        duplicator = ChannelDuplicator(config)

        # Setup signal handlers for graceful shutdown
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def signal_handler():
            logger.info("Received shutdown signal")
            loop.create_task(duplicator.stop())

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        # Run the duplicator
        loop.run_until_complete(duplicator.run())

    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
