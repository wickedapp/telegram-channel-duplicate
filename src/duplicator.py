import asyncio
import logging
from typing import Optional, Union

from telethon import TelegramClient, events
from telethon.tl.types import (
    Message,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
)
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

from .config import Config
from .filters import MessageFilter
from .transformer import TextTransformer

logger = logging.getLogger(__name__)


class ChannelDuplicator:
    """Core class for duplicating messages between Telegram channels."""

    def __init__(self, config: Config):
        self.config = config
        self.filter = MessageFilter(config)
        self.transformer = TextTransformer(config)

        # Initialize Telethon client
        self.client = TelegramClient(
            "duplicator_session",
            config.api_id,
            config.api_hash,
        )

        self._target_entity = None
        self._source_entities = {}

    async def start(self) -> None:
        """Start the duplicator client and register handlers."""
        logger.info("Starting Telegram client...")

        # Use lambda for interactive phone input if not set in .env
        phone = self.config.phone_number
        if phone:
            await self.client.start(phone=phone)
        else:
            # Prompt for phone number interactively
            await self.client.start(
                phone=lambda: input("请输入手机号码 (Please enter phone number, e.g. +8613812345678): ")
            )

        # Verify we're logged in
        me = await self.client.get_me()
        logger.info(f"Logged in as: {me.first_name} (@{me.username})")

        # Resolve target channel
        await self._resolve_target()

        # Resolve source channels and register handlers
        await self._register_handlers()

        logger.info("Duplicator is now running. Press Ctrl+C to stop.")

    async def _resolve_target(self) -> None:
        """Resolve target channel entity."""
        try:
            self._target_entity = await self.client.get_entity(
                self.config.target_channel
            )
            logger.info(f"Target channel resolved: {self.config.target_channel}")
        except Exception as e:
            logger.error(f"Failed to resolve target channel: {e}")
            raise

    async def _register_handlers(self) -> None:
        """Resolve source channels and register event handlers."""
        source_ids = []

        for channel in self.config.source_channels:
            try:
                entity = await self.client.get_entity(channel)
                self._source_entities[entity.id] = channel
                source_ids.append(entity.id)
                logger.info(f"Monitoring source channel: {channel}")
            except Exception as e:
                logger.error(f"Failed to resolve source channel '{channel}': {e}")

        if not source_ids:
            raise ValueError("No valid source channels found")

        # Register the new message handler
        @self.client.on(events.NewMessage(chats=source_ids))
        async def handler(event: events.NewMessage.Event):
            await self._handle_message(event.message)

    async def _handle_message(self, message: Message) -> None:
        """Process an incoming message."""
        source_name = self._source_entities.get(message.chat_id, "Unknown")

        # Apply filters
        should_copy, reason = self.filter.should_copy(message)

        if not should_copy:
            logger.debug(f"Skipping message from {source_name}: {reason}")
            return

        # Transform text
        original_text = message.text or getattr(message, 'caption', None) or ""
        transformed_text = self.transformer.transform(original_text)

        logger.info(
            f"Copying message from {source_name} "
            f"(ID: {message.id}, has_media: {message.media is not None})"
        )

        # Send to target
        await self._send_to_target(message, transformed_text)

    async def _send_to_target(
        self,
        message: Message,
        transformed_text: Optional[str],
    ) -> None:
        """Send the message to target channel."""
        try:
            if message.media:
                await self._send_media_message(message, transformed_text)
            else:
                await self._send_text_message(transformed_text)

            logger.info(f"Successfully copied message {message.id}")

        except FloodWaitError as e:
            logger.warning(f"Rate limited. Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds)
            # Retry after waiting
            await self._send_to_target(message, transformed_text)

        except ChatWriteForbiddenError:
            logger.error(
                f"Cannot write to target channel. "
                f"Make sure you have posting permissions."
            )

        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def _send_text_message(self, text: Optional[str]) -> None:
        """Send a text-only message."""
        if not text:
            return

        await self.client.send_message(
            self._target_entity,
            text,
        )

    def _get_document_filename(self, message: Message) -> Optional[str]:
        """Extract filename from a document message."""
        if not isinstance(message.media, MessageMediaDocument):
            return None

        document = message.media.document
        if not document or not document.attributes:
            return None

        for attr in document.attributes:
            if hasattr(attr, 'file_name'):
                return attr.file_name
        return None

    def _should_skip_file(self, filename: Optional[str]) -> bool:
        """Check if file should be skipped based on extension."""
        if not filename:
            return False

        skip_extensions = self.config.skip_file_extensions
        if not skip_extensions:
            return False

        filename_lower = filename.lower()
        return any(filename_lower.endswith(ext.lower()) for ext in skip_extensions)

    async def _send_media_message(
        self,
        message: Message,
        caption: Optional[str],
    ) -> None:
        """Send a message with media."""
        media = message.media

        # Skip web page previews - just send text
        if isinstance(media, MessageMediaWebPage):
            if caption:
                await self._send_text_message(caption)
            return

        # Skip .rar and .zip files
        filename = self._get_document_filename(message)
        if self._should_skip_file(filename):
            logger.info(f"Skipping file with excluded extension: {filename}")
            return

        # Download and re-upload media
        # This is more reliable than forwarding
        file = await self.client.download_media(message, file=bytes)

        if file:
            await self.client.send_file(
                self._target_entity,
                file,
                caption=caption,
                # Preserve voice/video note attributes if present
                voice_note=getattr(message.media, "voice", False)
                if hasattr(message.media, "voice")
                else False,
                video_note=getattr(message.media, "round", False)
                if hasattr(message.media, "round")
                else False,
            )
        elif caption:
            # Media download failed, send text only
            await self._send_text_message(caption)

    async def run(self) -> None:
        """Run the duplicator until stopped."""
        await self.start()
        await self.client.run_until_disconnected()

    async def stop(self) -> None:
        """Stop the duplicator."""
        logger.info("Stopping duplicator...")
        await self.client.disconnect()
