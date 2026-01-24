"""
MySQL Message Logger for Telegram

Logs all Telegram messages to MySQL for debugging purposes.
Runs in a background thread to avoid blocking the main event loop.
"""

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from telethon import TelegramClient, events
from telethon.tl.types import (
    Message,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    MessageMediaGeo,
    MessageMediaContact,
    MessageMediaPoll,
    MessageMediaVenue,
    MessageMediaGame,
    MessageMediaInvoice,
    MessageMediaDice,
)

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    MySQLError = Exception

# Import db_config - handle both bundled and development modes
try:
    from db_config import MYSQL_CONFIG
except ImportError:
    try:
        from .db_config import MYSQL_CONFIG
    except ImportError:
        from installer.db_config import MYSQL_CONFIG

logger = logging.getLogger(__name__)


# SQL for creating the messages table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS telegram_messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_date DATETIME,
    chat_id BIGINT,
    chat_name VARCHAR(255),
    sender_id BIGINT,
    sender_name VARCHAR(255),
    message_id BIGINT,
    message_text TEXT,
    media_type VARCHAR(50),
    is_outgoing BOOLEAN,
    raw_json JSON,
    INDEX idx_chat_id (chat_id),
    INDEX idx_message_date (message_date)
)
"""

INSERT_MESSAGE_SQL = """
INSERT INTO telegram_messages
    (message_date, chat_id, chat_name, sender_id, sender_name,
     message_id, message_text, media_type, is_outgoing, raw_json)
VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


@dataclass
class MessageRecord:
    """Data class for a message to be logged."""
    message_date: datetime
    chat_id: int
    chat_name: str
    sender_id: Optional[int]
    sender_name: str
    message_id: int
    message_text: Optional[str]
    media_type: Optional[str]
    is_outgoing: bool
    raw_json: str

    def to_tuple(self) -> tuple:
        """Convert to tuple for SQL insertion."""
        return (
            self.message_date,
            self.chat_id,
            self.chat_name,
            self.sender_id,
            self.sender_name,
            self.message_id,
            self.message_text,
            self.media_type,
            self.is_outgoing,
            self.raw_json,
        )


class MessageLogger:
    """
    Logs Telegram messages to MySQL database.

    Attaches to a Telethon client and captures all messages (incoming and outgoing)
    from all chats. Runs database operations in a background thread to avoid
    blocking the event loop.
    """

    def __init__(
        self,
        client: TelegramClient,
        config: Optional[dict] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        max_queue_size: int = 10000,
    ):
        """
        Initialize the message logger.

        Args:
            client: The Telethon TelegramClient to attach to.
            config: MySQL configuration dict. Defaults to MYSQL_CONFIG.
            max_retries: Maximum number of retry attempts for DB operations.
            retry_delay: Delay in seconds between retry attempts.
            max_queue_size: Maximum size of the message queue.
        """
        if not MYSQL_AVAILABLE:
            raise ImportError(
                "mysql-connector-python is required for MessageLogger. "
                "Install it with: pip install mysql-connector-python"
            )

        self.client = client
        self.config = config or MYSQL_CONFIG
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Message queue for background processing
        self._queue: queue.Queue[Optional[MessageRecord]] = queue.Queue(
            maxsize=max_queue_size
        )

        # Background thread for DB operations
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

        # Database connection (managed by worker thread)
        self._connection: Optional[Any] = None

        # Event handlers
        self._incoming_handler = None
        self._outgoing_handler = None

        # Chat name cache to avoid repeated API calls
        self._chat_cache: dict[int, str] = {}
        self._cache_lock = threading.Lock()

    def _get_media_type(self, message: Message) -> Optional[str]:
        """Extract media type from a message."""
        if not message.media:
            return None

        media = message.media
        media_type_map = {
            MessageMediaPhoto: "photo",
            MessageMediaDocument: "document",
            MessageMediaWebPage: "webpage",
            MessageMediaGeo: "geo",
            MessageMediaContact: "contact",
            MessageMediaPoll: "poll",
            MessageMediaVenue: "venue",
            MessageMediaGame: "game",
            MessageMediaInvoice: "invoice",
            MessageMediaDice: "dice",
        }

        for media_class, type_name in media_type_map.items():
            if isinstance(media, media_class):
                # For documents, try to get more specific type
                if isinstance(media, MessageMediaDocument) and media.document:
                    doc = media.document
                    if hasattr(doc, 'mime_type') and doc.mime_type:
                        # e.g., "document/video", "document/audio"
                        return f"document/{doc.mime_type.split('/')[0]}"
                return type_name

        return type(media).__name__

    def _message_to_raw_json(self, message: Message) -> str:
        """Convert message to JSON for raw_json field."""
        try:
            # Create a serializable dict with key message attributes
            raw_data = {
                "id": message.id,
                "date": message.date.isoformat() if message.date else None,
                "chat_id": message.chat_id,
                "from_id": getattr(message.from_id, 'user_id', None) if message.from_id else None,
                "text": message.text,
                "out": message.out,
                "grouped_id": message.grouped_id,
                "reply_to_msg_id": message.reply_to.reply_to_msg_id if message.reply_to else None,
                "fwd_from": bool(message.fwd_from),
                "media_type": self._get_media_type(message),
                "entities_count": len(message.entities) if message.entities else 0,
            }
            return json.dumps(raw_data, default=str)
        except Exception as e:
            logger.warning(f"Failed to serialize message to JSON: {e}")
            return json.dumps({"error": str(e), "message_id": message.id})

    async def _get_chat_name(self, message: Message) -> str:
        """Get chat name from message, with caching."""
        chat_id = message.chat_id

        # Check cache first
        with self._cache_lock:
            if chat_id in self._chat_cache:
                return self._chat_cache[chat_id]

        # Try to get chat name
        chat_name = "Unknown"
        try:
            chat = await message.get_chat()
            if chat:
                if hasattr(chat, 'title') and chat.title:
                    chat_name = chat.title
                elif hasattr(chat, 'first_name'):
                    chat_name = chat.first_name
                    if hasattr(chat, 'last_name') and chat.last_name:
                        chat_name = f"{chat_name} {chat.last_name}"
                elif hasattr(chat, 'username') and chat.username:
                    chat_name = f"@{chat.username}"
        except Exception as e:
            logger.debug(f"Could not get chat name for {chat_id}: {e}")

        # Cache the result
        with self._cache_lock:
            self._chat_cache[chat_id] = chat_name

        return chat_name

    async def _get_sender_info(self, message: Message) -> tuple[Optional[int], str]:
        """Get sender ID and name from message."""
        sender_id = None
        sender_name = "Unknown"

        try:
            sender = await message.get_sender()
            if sender:
                sender_id = sender.id
                if hasattr(sender, 'first_name') and sender.first_name:
                    sender_name = sender.first_name
                    if hasattr(sender, 'last_name') and sender.last_name:
                        sender_name = f"{sender_name} {sender.last_name}"
                elif hasattr(sender, 'title') and sender.title:
                    sender_name = sender.title
                elif hasattr(sender, 'username') and sender.username:
                    sender_name = f"@{sender.username}"
        except Exception as e:
            logger.debug(f"Could not get sender info: {e}")

        return sender_id, sender_name

    async def _handle_message(self, event: events.NewMessage.Event) -> None:
        """Handle incoming/outgoing message event."""
        try:
            message = event.message

            # Get chat and sender info
            chat_name = await self._get_chat_name(message)
            sender_id, sender_name = await self._get_sender_info(message)

            # Get message text (text or caption)
            message_text = message.text or getattr(message, 'caption', None)

            # Create record
            record = MessageRecord(
                message_date=message.date,
                chat_id=message.chat_id,
                chat_name=chat_name,
                sender_id=sender_id,
                sender_name=sender_name,
                message_id=message.id,
                message_text=message_text,
                media_type=self._get_media_type(message),
                is_outgoing=message.out,
                raw_json=self._message_to_raw_json(message),
            )

            # Queue for background processing
            try:
                self._queue.put_nowait(record)
            except queue.Full:
                logger.warning("Message queue is full, dropping oldest message")
                # Remove oldest and add new
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(record)
                except queue.Empty:
                    pass

        except Exception as e:
            logger.error(f"Error handling message for logging: {e}")

    def _connect_db(self) -> bool:
        """Establish database connection. Returns True on success."""
        try:
            self._connection = mysql.connector.connect(**self.config)
            self._connection.autocommit = True
            logger.info("MySQL connection established for message logging")
            return True
        except MySQLError as e:
            logger.error(f"Failed to connect to MySQL: {e}")
            self._connection = None
            return False

    def _ensure_table_exists(self) -> bool:
        """Create the messages table if it doesn't exist. Returns True on success."""
        if not self._connection:
            return False

        try:
            cursor = self._connection.cursor()
            cursor.execute(CREATE_TABLE_SQL)
            cursor.close()
            logger.info("Ensured telegram_messages table exists")
            return True
        except MySQLError as e:
            logger.error(f"Failed to create table: {e}")
            return False

    def _insert_record(self, record: MessageRecord) -> bool:
        """Insert a message record into database. Returns True on success."""
        if not self._connection:
            return False

        try:
            cursor = self._connection.cursor()
            cursor.execute(INSERT_MESSAGE_SQL, record.to_tuple())
            cursor.close()
            return True
        except MySQLError as e:
            logger.error(f"Failed to insert message record: {e}")
            # Check if connection is still alive
            try:
                self._connection.ping(reconnect=False)
            except MySQLError:
                logger.warning("MySQL connection lost, will reconnect")
                self._connection = None
            return False

    def _worker_loop(self) -> None:
        """Background worker thread loop for processing message queue."""
        logger.info("Message logger worker thread started")

        # Local queue for failed inserts (for retry)
        retry_queue: list[MessageRecord] = []

        while self._running or not self._queue.empty() or retry_queue:
            # Try to connect if not connected
            if not self._connection:
                if not self._connect_db():
                    # Connection failed, wait before retry
                    time.sleep(self.retry_delay)
                    continue

                # Ensure table exists
                if not self._ensure_table_exists():
                    self._connection = None
                    time.sleep(self.retry_delay)
                    continue

            # Process retry queue first
            if retry_queue:
                still_failed = []
                for record in retry_queue:
                    if not self._insert_record(record):
                        still_failed.append(record)
                retry_queue = still_failed

                if still_failed:
                    # Some inserts still failing, wait a bit
                    time.sleep(self.retry_delay)
                    continue

            # Get next message from queue
            try:
                record = self._queue.get(timeout=1.0)

                # None is the shutdown signal
                if record is None:
                    break

                # Try to insert
                if not self._insert_record(record):
                    # Add to retry queue
                    retry_queue.append(record)

                    # Limit retry queue size to prevent memory issues
                    if len(retry_queue) > 1000:
                        dropped = len(retry_queue) - 1000
                        retry_queue = retry_queue[-1000:]
                        logger.warning(f"Retry queue overflow, dropped {dropped} records")

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in message logger worker: {e}")

        # Clean up
        if self._connection:
            try:
                self._connection.close()
                logger.info("MySQL connection closed")
            except Exception:
                pass

        logger.info("Message logger worker thread stopped")

    def start(self) -> None:
        """
        Start the message logger.

        Attaches event handlers to the Telethon client and starts the
        background worker thread.
        """
        if self._running:
            logger.warning("Message logger is already running")
            return

        self._running = True

        # Register event handlers for all messages (incoming and outgoing)
        @self.client.on(events.NewMessage(incoming=True))
        async def incoming_handler(event):
            await self._handle_message(event)

        @self.client.on(events.NewMessage(outgoing=True))
        async def outgoing_handler(event):
            await self._handle_message(event)

        self._incoming_handler = incoming_handler
        self._outgoing_handler = outgoing_handler

        # Start worker thread
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="MessageLoggerWorker",
            daemon=True,
        )
        self._worker_thread.start()

        logger.info("Message logger started")

    def stop(self, timeout: float = 10.0) -> None:
        """
        Stop the message logger.

        Args:
            timeout: Maximum time to wait for worker thread to finish.
        """
        if not self._running:
            return

        logger.info("Stopping message logger...")
        self._running = False

        # Send shutdown signal to worker
        try:
            self._queue.put(None, timeout=1.0)
        except queue.Full:
            pass

        # Wait for worker to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                logger.warning("Message logger worker thread did not stop gracefully")

        # Remove event handlers
        if self._incoming_handler:
            self.client.remove_event_handler(self._incoming_handler)
        if self._outgoing_handler:
            self.client.remove_event_handler(self._outgoing_handler)

        logger.info("Message logger stopped")

    @property
    def is_running(self) -> bool:
        """Check if the message logger is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get current message queue size."""
        return self._queue.qsize()


def create_message_logger(
    client: TelegramClient,
    config: Optional[dict] = None,
    auto_start: bool = True,
) -> Optional[MessageLogger]:
    """
    Factory function to create and optionally start a message logger.

    Args:
        client: The Telethon TelegramClient to attach to.
        config: MySQL configuration dict. Defaults to MYSQL_CONFIG.
        auto_start: Whether to start the logger immediately.

    Returns:
        MessageLogger instance, or None if MySQL is not available.
    """
    if not MYSQL_AVAILABLE:
        logger.warning(
            "MySQL connector not available, message logging disabled. "
            "Install with: pip install mysql-connector-python"
        )
        return None

    try:
        message_logger = MessageLogger(client, config=config)
        if auto_start:
            message_logger.start()
        return message_logger
    except Exception as e:
        logger.error(f"Failed to create message logger: {e}")
        return None
