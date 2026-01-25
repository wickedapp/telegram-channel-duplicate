"""
Config Manager for Telegram Channel Duplicator Installer

Handles reading and writing configuration files (.env and config.yaml)
for the Windows setup wizard.
"""

import sys
from pathlib import Path

import yaml


# Get the project root directory
# When bundled with PyInstaller, use the directory where the .exe is located
# When running as script, use the parent of installer/
if getattr(sys, 'frozen', False):
    # Running as bundled executable
    PROJECT_ROOT = Path(sys.executable).parent
else:
    # Running as script
    PROJECT_ROOT = Path(__file__).parent.parent

ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = PROJECT_ROOT / "config.yaml"


def config_exists() -> dict:
    """
    Check if .env and config.yaml exist.

    Returns:
        dict with 'env' and 'config' boolean keys indicating existence
    """
    return {
        "env": ENV_FILE.exists(),
        "config": CONFIG_FILE.exists(),
    }


def load_config() -> dict:
    """
    Read current configuration from both .env and config.yaml.

    Returns:
        dict with:
            - api_id: str or None
            - api_hash: str or None
            - target_channel: str or None
            - my_channel_name: str or None
            - my_username: str or None
            - my_contact_username: str or None
            - source_channels: list or []
            - full_config: complete config.yaml dict (for preserving other settings)
    """
    result = {
        "api_id": None,
        "api_hash": None,
        "target_channel": None,
        "my_channel_name": None,
        "my_username": None,
        "my_contact_username": None,
        "source_channels": [],
        "full_config": None,
    }

    # Load .env file
    if ENV_FILE.exists():
        env_data = _parse_env_file(ENV_FILE)
        result["api_id"] = env_data.get("API_ID")
        result["api_hash"] = env_data.get("API_HASH")

    # Load config.yaml
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        result["target_channel"] = config_data.get("target_channel")
        result["my_channel_name"] = config_data.get("my_channel_name")
        result["my_username"] = config_data.get("my_username")
        result["my_contact_username"] = config_data.get("my_contact_username")
        result["source_channels"] = config_data.get("source_channels", [])
        result["full_config"] = config_data

    return result


def _parse_env_file(env_path: Path) -> dict:
    """
    Parse a .env file into a dictionary.

    Args:
        env_path: Path to the .env file

    Returns:
        dict of environment variables
    """
    env_vars = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                env_vars[key] = value
    return env_vars


def save_env(api_id: str, api_hash: str) -> None:
    """
    Write .env file with API credentials.

    Args:
        api_id: Telegram API ID
        api_hash: Telegram API Hash
    """
    content = f"""# Telegram API credentials
# Get these from https://my.telegram.org
API_ID={api_id}
API_HASH={api_hash}

# Optional: Phone number for first-time login
# PHONE_NUMBER=+1234567890
"""
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def save_config(
    target: str,
    name: str,
    username: str,
    contact: str,
    sources: list,
) -> None:
    """
    Update config.yaml with user-specific fields while preserving other settings.

    Preserves existing sections like replacements, negative_filters, message_filters.

    Args:
        target: Target channel (e.g., "@mychannel")
        name: Channel display name (e.g., "My Channel Name")
        username: Channel username (e.g., "@mychannel")
        contact: Contact username (e.g., "@mycontact")
        sources: List of source channels to monitor
    """
    # Load existing config to preserve other settings
    existing_config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f) or {}

    # Update user-specific fields
    existing_config["target_channel"] = target
    existing_config["my_channel_name"] = name
    existing_config["my_username"] = username
    existing_config["my_contact_username"] = contact
    existing_config["source_channels"] = sources if sources else []

    # Ensure default sections exist if this is a fresh config
    if "replacements" not in existing_config:
        existing_config["replacements"] = _get_default_replacements()

    if "negative_filters" not in existing_config:
        existing_config["negative_filters"] = _get_default_negative_filters()

    if "message_filters" not in existing_config:
        existing_config["message_filters"] = _get_default_message_filters()

    if "log_level" not in existing_config:
        existing_config["log_level"] = "INFO"

    # Write config with comments
    _write_config_with_comments(existing_config)


def _get_default_replacements() -> list:
    """Return default replacement rules."""
    return [
        {
            "pattern": "📣订阅.*?频道.*?↓",
            "replace": "📣订阅{{my_channel_name}}频道 🌐↓",
        },
        {
            "pattern": "🔗\\s*@\\w+",
            "replace": "🔗 {{my_username}}",
        },
        {
            "pattern": "[^\\n]*投稿[^\\n：:]*[：:]\\s*@\\w+",
            "replace": "投稿澄清爆料：{{my_contact_username}}",
        },
        {
            "pattern": "客服.*?@\\w+",
            "replace": "客服：{{my_contact_username}}",
        },
        {
            "pattern": "✈️+\\s*@\\w+",
            "replace": "✈️ {{my_contact_username}}",
        },
        {
            "pattern": "@DC18777",
            "replace": "{{my_contact_username}}",
        },
    ]


def _get_default_negative_filters() -> dict:
    """Return default negative filter settings."""
    return {
        "keywords": [
            "广告",
            "推广",
            "招代理",
            "招商",
            "免费领",
            "日入过万",
        ],
        "patterns": [
            "赚钱.*?日入",
            "免费.*?红包",
            "点击.*?链接.*?领取",
        ],
    }


def _get_default_message_filters() -> dict:
    """Return default message filter settings."""
    return {
        "ignore_forwarded": True,
        "min_length": 0,
        "max_length": 0,
        "skip_file_extensions": [".rar", ".zip"],
        "require_keywords": None,
    }


def _yaml_escape(value: str) -> str:
    """
    Escape a string value for YAML double-quoted format.

    Args:
        value: String to escape

    Returns:
        Escaped string safe for YAML double-quoted context
    """
    # In YAML double-quoted strings, backslashes must be escaped
    # This ensures patterns like \s, \w+, \\n are preserved correctly
    escaped = value.replace("\\", "\\\\")
    # Also escape double quotes
    escaped = escaped.replace('"', '\\"')
    return escaped


def _write_config_with_comments(config: dict) -> None:
    """
    Write config.yaml with helpful comments.

    Args:
        config: Configuration dictionary to write
    """
    lines = [
        "# Telegram Channel Duplicator Configuration",
        "# Telegram 频道复制器配置",
        "",
        "# Target channel to post messages to",
        "# 目标频道 - 消息将发送到这个频道",
        f"target_channel: \"{_yaml_escape(config.get('target_channel', ''))}\"",
        "",
        "# Your channel/user info for text replacements",
        "# 你的频道/用户信息 - 用于文字替换",
        f"my_channel_name: \"{_yaml_escape(config.get('my_channel_name', ''))}\"",
        f"my_username: \"{_yaml_escape(config.get('my_username', ''))}\"",
        f"my_contact_username: \"{_yaml_escape(config.get('my_contact_username', ''))}\"",
        "",
        "# Source channels to monitor",
        "# 来源频道 - 监控这些频道的新消息",
        "source_channels:",
    ]

    # Add source channels
    sources = config.get("source_channels", [])
    if sources:
        for source in sources:
            lines.append(f"  - \"{_yaml_escape(source)}\"")
    else:
        lines.append("  []")

    lines.extend([
        "",
        "# Text replacements (applied in order)",
        "# 文字替换规则 (按顺序执行)",
        "# 使用正则表达式。变量: {{my_channel_name}}, {{my_username}}, {{my_contact_username}}",
        "replacements:",
    ])

    # Add replacements
    replacements = config.get("replacements", [])
    for rep in replacements:
        pattern = rep.get("pattern", "")
        replace = rep.get("replace", "")
        lines.append(f"  - pattern: \"{_yaml_escape(pattern)}\"")
        lines.append(f"    replace: \"{_yaml_escape(replace)}\"")
        lines.append("")

    lines.extend([
        "# Negative filters - messages matching these will be IGNORED",
        "# 负面过滤器 - 匹配这些规则的消息将被忽略",
        "negative_filters:",
        "  # Keyword blocklist (case-insensitive substring match)",
        "  # 关键词黑名单 (不区分大小写)",
        "  keywords:",
    ])

    # Add negative filter keywords
    neg_filters = config.get("negative_filters", {})
    keywords = neg_filters.get("keywords", [])
    for kw in keywords:
        lines.append(f"    - \"{_yaml_escape(kw)}\"")

    lines.extend([
        "",
        "  # Regex patterns for more complex filtering",
        "  # 正则表达式过滤 (更复杂的过滤规则)",
        "  patterns:",
    ])

    # Add negative filter patterns
    patterns = neg_filters.get("patterns", [])
    for pat in patterns:
        lines.append(f"    - \"{_yaml_escape(pat)}\"")

    lines.extend([
        "",
        "# Message filter settings",
        "# 消息过滤设置",
        "message_filters:",
        "  # Ignore forwarded messages (only copy original posts)",
        "  # 忽略转发的消息 (只复制原创帖子)",
    ])

    msg_filters = config.get("message_filters", {})
    ignore_fwd = msg_filters.get("ignore_forwarded", True)
    lines.append(f"  ignore_forwarded: {str(ignore_fwd).lower()}")

    lines.extend([
        "",
        "  # Minimum message length (0 = no minimum)",
        "  # 最小消息长度 (0 = 无限制)",
    ])
    lines.append(f"  min_length: {msg_filters.get('min_length', 0)}")

    lines.extend([
        "",
        "  # Maximum message length (0 = no limit)",
        "  # 最大消息长度 (0 = 无限制)",
    ])
    lines.append(f"  max_length: {msg_filters.get('max_length', 0)}")

    lines.extend([
        "",
        "  # File extensions to skip (won't copy these files)",
        "  # 跳过的文件扩展名 (不复制这些文件)",
        "  skip_file_extensions:",
    ])

    skip_exts = msg_filters.get("skip_file_extensions", [])
    for ext in skip_exts:
        lines.append(f"    - \"{_yaml_escape(ext)}\"")

    lines.extend([
        "",
        "  # Required keywords - ONLY copy messages containing at least one of these",
        "  # 必须包含的关键词 - 只复制包含这些关键词的消息 (留空则复制所有消息)",
        "  require_keywords:",
    ])

    req_keywords = msg_filters.get("require_keywords")
    if req_keywords:
        for kw in req_keywords:
            lines.append(f"    - \"{_yaml_escape(kw)}\"")

    lines.extend([
        "",
        "# Logging level: DEBUG, INFO, WARNING, ERROR",
        "# 日志级别",
        f"log_level: {config.get('log_level', 'INFO')}",
        "",
    ])

    # Write the file
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
