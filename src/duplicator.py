import asyncio
import logging
from typing import Optional, Union
from collections import defaultdict

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

# Time to wait for collecting media group messages (seconds)
MEDIA_GROUP_WAIT_TIME = 1.0


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

        # For handling media groups (albums)
        self._media_groups: dict[int, list[Message]] = defaultdict(list)
        self._media_group_tasks: dict[int, asyncio.Task] = {}

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

        # Log raw message details for debugging
        text = message.text or ""
        caption = getattr(message, 'caption', None) or ""
        grouped_id = getattr(message, 'grouped_id', None)
        has_media = message.media is not None
        media_type = type(message.media).__name__ if message.media else "None"
        is_forwarded = message.fwd_from is not None

        logger.info(
            f"[RAW MESSAGE] source={source_name} id={message.id} "
            f"grouped_id={grouped_id} has_media={has_media} media_type={media_type} "
            f"is_forwarded={is_forwarded} text_len={len(text)} caption_len={len(caption)}"
        )
        logger.info(f"[RAW MESSAGE] text={repr(text[:200])}{'...' if len(text) > 200 else ''}")
        if caption:
            logger.info(f"[RAW MESSAGE] caption={repr(caption[:200])}{'...' if len(caption) > 200 else ''}")

        if grouped_id:
            # For media groups, collect all messages first, then filter
            # (caption may only be on one message in the group)
            self._media_groups[grouped_id].append(message)

            # Cancel existing task for this group if any
            if grouped_id in self._media_group_tasks:
                self._media_group_tasks[grouped_id].cancel()

            # Schedule processing after a short delay to collect all messages
            self._media_group_tasks[grouped_id] = asyncio.create_task(
                self._process_media_group_delayed(grouped_id, source_name)
            )
            return

        # For non-media-group messages, apply filters here
        should_copy, reason = self.filter.should_copy(message)
        logger.info(f"[FILTER] msg_id={message.id} should_copy={should_copy} reason='{reason}'")

        if not should_copy:
            logger.info(f"Skipping message from {source_name}: {reason}")
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

    async def _process_media_group_delayed(self, grouped_id: int, source_name: str) -> None:
        """Wait for all messages in a media group, then process them together."""
        await asyncio.sleep(MEDIA_GROUP_WAIT_TIME)

        messages = self._media_groups.pop(grouped_id, [])
        self._media_group_tasks.pop(grouped_id, None)

        if not messages:
            return

        # Sort by message ID to maintain order
        messages.sort(key=lambda m: m.id)

        # Log media group details
        logger.info(
            f"[MEDIA GROUP] grouped_id={grouped_id} count={len(messages)} "
            f"message_ids={[m.id for m in messages]}"
        )
        for msg in messages:
            msg_text = msg.text or ""
            msg_caption = getattr(msg, 'caption', None) or ""
            logger.info(
                f"[MEDIA GROUP] msg_id={msg.id} text_len={len(msg_text)} "
                f"caption_len={len(msg_caption)} media_type={type(msg.media).__name__ if msg.media else 'None'}"
            )

        # Get caption from the first message that has one
        caption_text = None
        caption_msg = None
        for msg in messages:
            text = msg.text or getattr(msg, 'caption', None)
            if text:
                caption_text = text
                caption_msg = msg
                logger.info(f"[MEDIA GROUP] found caption in msg_id={msg.id}: {repr(text[:200])}{'...' if len(text) > 200 else ''}")
                break

        # Apply filters using the message with caption (or first message if no caption)
        filter_msg = caption_msg if caption_msg else messages[0]
        should_copy, reason = self.filter.should_copy(filter_msg)

        logger.info(f"[MEDIA GROUP] filter result: should_copy={should_copy} reason='{reason}'")

        if not should_copy:
            logger.info(f"Skipping media group from {source_name}: {reason}")
            return

        # Transform the caption
        transformed_caption = self.transformer.transform(caption_text) if caption_text else None

        logger.info(
            f"Copying media group from {source_name} "
            f"({len(messages)} items, IDs: {[m.id for m in messages]})"
        )

        await self._send_media_group(messages, transformed_caption)

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

    async def _send_media_group(
        self,
        messages: list[Message],
        caption: Optional[str],
    ) -> None:
        """Send a media group (album) to target channel."""
        try:
            # Collect all media files
            files = []
            for msg in messages:
                if isinstance(msg.media, MessageMediaPhoto):
                    # Use photo directly to preserve type
                    files.append(msg.photo)
                elif isinstance(msg.media, MessageMediaDocument):
                    # Check if should skip this file
                    filename = self._get_document_filename(msg)
                    if self._should_skip_file(filename):
                        logger.info(f"Skipping file with excluded extension: {filename}")
                        continue
                    files.append(msg.document)

            if not files:
                # All files were skipped, just send caption if any
                if caption:
                    await self._send_text_message(caption)
                return

            # Send all files as an album
            await self.client.send_file(
                self._target_entity,
                files,
                caption=caption,
            )
            logger.info(f"Successfully copied media group ({len(files)} items)")

        except FloodWaitError as e:
            logger.warning(f"Rate limited. Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds)
            await self._send_media_group(messages, caption)

        except Exception as e:
            logger.error(f"Failed to send media group: {e}")

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

        # Skip files with excluded extensions
        filename = self._get_document_filename(message)
        if self._should_skip_file(filename):
            logger.info(f"Skipping file with excluded extension: {filename}")
            return

        # For photos, use the photo object directly to preserve type
        if isinstance(media, MessageMediaPhoto):
            await self.client.send_file(
                self._target_entity,
                message.photo,
                caption=caption,
            )
        elif isinstance(media, MessageMediaDocument):
            # For documents, use the document object directly
            await self.client.send_file(
                self._target_entity,
                message.document,
                caption=caption,
                voice_note=getattr(media, "voice", False)
                if hasattr(media, "voice")
                else False,
                video_note=getattr(media, "round", False)
                if hasattr(media, "round")
                else False,
            )
        else:
            # For other media types, try downloading and sending
            file = await self.client.download_media(message, file=bytes)
            if file:
                await self.client.send_file(
                    self._target_entity,
                    file,
                    caption=caption,
                )
            elif caption:
                await self._send_text_message(caption)

    async def run(self) -> None:
        """Run the duplicator until stopped."""
        await self.start()
        await self.client.run_until_disconnected()

    async def stop(self) -> None:
        """Stop the duplicator."""
        logger.info("Stopping duplicator...")
        await self.client.disconnect()
