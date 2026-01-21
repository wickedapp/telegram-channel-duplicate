import re
import logging
from typing import Optional

from telethon.tl.types import Message

from .config import Config

logger = logging.getLogger(__name__)


class MessageFilter:
    """Filter messages based on configured rules."""

    def __init__(self, config: Config):
        self.config = config
        # Pre-compile regex patterns for performance
        self._compiled_patterns: list[re.Pattern] = []
        for pattern in config.negative_patterns:
            try:
                self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")

    def is_forwarded(self, message: Message) -> bool:
        """Check if message is forwarded."""
        return message.fwd_from is not None

    def matches_required_keyword(self, text: str) -> bool:
        """
        Check if text contains at least one required keyword.
        Returns True if a required keyword is found, or if no required keywords are configured.
        """
        required = self.config.require_keywords
        if not required:
            # No required keywords configured, allow all
            return True

        if not text:
            return False

        for keyword in required:
            if keyword in text:
                return True
        return False

    def matches_negative_keyword(self, text: str) -> Optional[str]:
        """
        Check if text contains any negative keyword.
        Returns the matched keyword or None.
        """
        if not text:
            return None

        text_lower = text.lower()
        for keyword in self.config.negative_keywords:
            if keyword.lower() in text_lower:
                return keyword
        return None

    def matches_negative_pattern(self, text: str) -> Optional[str]:
        """
        Check if text matches any negative regex pattern.
        Returns the matched pattern or None.
        """
        if not text:
            return None

        for pattern in self._compiled_patterns:
            if pattern.search(text):
                return pattern.pattern
        return None

    def check_length(self, text: str) -> bool:
        """
        Check if text length is within configured limits.
        Returns True if valid, False otherwise.
        """
        if not text:
            text = ""

        length = len(text)

        if self.config.min_length > 0 and length < self.config.min_length:
            return False

        if self.config.max_length > 0 and length > self.config.max_length:
            return False

        return True

    def should_copy(self, message: Message) -> tuple[bool, str]:
        """
        Determine if a message should be copied.

        Returns:
            tuple: (should_copy: bool, reason: str)
            - If should_copy is True, reason is empty
            - If should_copy is False, reason explains why
        """
        text = message.text or getattr(message, 'caption', None) or ""

        # Check if forwarded
        if self.config.ignore_forwarded and self.is_forwarded(message):
            return False, "Message is forwarded"

        # Check required keywords (whitelist) - must contain at least one
        if not self.matches_required_keyword(text):
            return False, "Missing required keyword"

        # Check negative keywords (blacklist)
        matched_keyword = self.matches_negative_keyword(text)
        if matched_keyword:
            return False, f"Matched negative keyword: '{matched_keyword}'"

        # Check negative patterns
        matched_pattern = self.matches_negative_pattern(text)
        if matched_pattern:
            return False, f"Matched negative pattern: '{matched_pattern}'"

        # Check length
        if not self.check_length(text):
            return False, f"Message length ({len(text)}) outside limits"

        return True, ""
