import re
import logging
from typing import Optional

from .config import Config

logger = logging.getLogger(__name__)


class TextTransformer:
    """Transform message text with configured replacements."""

    def __init__(self, config: Config):
        self.config = config
        self.template_vars = config.get_template_vars()

        # Pre-compile replacement patterns
        self._replacements: list[tuple[re.Pattern, str]] = []
        for rule in config.replacements:
            pattern = rule.get("pattern", "")
            replace = rule.get("replace", "")

            if not pattern:
                continue

            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
                # Substitute template variables in replacement string
                replace = self._substitute_template(replace)
                self._replacements.append((compiled, replace))
            except re.error as e:
                logger.warning(f"Invalid replacement pattern '{pattern}': {e}")

    def _substitute_template(self, text: str) -> str:
        """Substitute {{variable}} templates with actual values."""
        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            return self.template_vars.get(var_name, match.group(0))

        return re.sub(r"\{\{(\w+)\}\}", replacer, text)

    def transform(self, text: Optional[str]) -> Optional[str]:
        """
        Apply all configured replacements to the text.

        Args:
            text: Original message text

        Returns:
            Transformed text with all replacements applied
        """
        if not text:
            return text

        result = text

        for pattern, replacement in self._replacements:
            try:
                new_result = pattern.sub(replacement, result)
                if new_result != result:
                    logger.debug(
                        f"Applied replacement: '{pattern.pattern}' -> '{replacement}'"
                    )
                result = new_result
            except Exception as e:
                logger.error(f"Error applying replacement '{pattern.pattern}': {e}")

        return result

    def has_changes(self, original: Optional[str], transformed: Optional[str]) -> bool:
        """Check if text was actually modified."""
        return original != transformed
