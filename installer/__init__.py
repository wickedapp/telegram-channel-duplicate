"""
Telegram Channel Duplicator Windows Installer Components

This package contains modules for the Windows installer:
- db_config: MySQL database configuration
- message_logger: MySQL message logging for debugging
- config_manager: Configuration file management
- setup_wizard: Tkinter 4-step configuration wizard
- tray_app: System tray application (main entry point)
"""

from .db_config import MYSQL_CONFIG

__all__ = ["MYSQL_CONFIG"]
