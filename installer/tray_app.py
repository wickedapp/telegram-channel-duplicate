"""
System Tray Application for Telegram Channel Duplicator

Main entry point for Windows users. Provides a system tray icon with:
- Green icon: Running
- Red icon: Stopped
- Yellow icon: Connecting

Right-click menu:
- Start / Stop
- Edit Config (opens config.yaml in notepad)
- View Logs (opens log window)
- Re-setup (re-run setup wizard)
- Exit

Double-click toggles start/stop.
"""

import asyncio
import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from queue import Empty, Queue
from tkinter import scrolledtext
from typing import Optional

# Determine if we're running as a bundled executable or as a script
if getattr(sys, 'frozen', False):
    # Running as bundled executable (PyInstaller)
    BUNDLE_DIR = Path(sys._MEIPASS)
    PROJECT_ROOT = Path(sys.executable).parent
    # Add bundled directories to path
    sys.path.insert(0, str(BUNDLE_DIR))
    sys.path.insert(0, str(BUNDLE_DIR / 'src'))
    sys.path.insert(0, str(BUNDLE_DIR / 'installer'))
else:
    # Running as script
    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / 'src'))
    sys.path.insert(0, str(PROJECT_ROOT / 'installer'))

from PIL import Image

try:
    import pystray
    from pystray import Icon, Menu, MenuItem
except ImportError:
    print("pystray is required. Install with: pip install pystray")
    sys.exit(1)

# Import config_manager - handle both bundled and development modes
try:
    from config_manager import config_exists, CONFIG_FILE, ENV_FILE
except ImportError:
    from installer.config_manager import config_exists, CONFIG_FILE, ENV_FILE

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Icon states
class IconState:
    """Enum-like class for tray icon states."""
    STOPPED = "stopped"
    RUNNING = "running"
    CONNECTING = "connecting"


class LogWindow:
    """A simple log viewer window using Tkinter."""

    def __init__(self):
        self.window: Optional[tk.Tk] = None
        self.text_widget: Optional[scrolledtext.ScrolledText] = None
        self.log_queue: Queue = Queue()
        self._is_open = False
        self._lock = threading.Lock()

    def open(self) -> None:
        """Open the log window in a new thread."""
        with self._lock:
            if self._is_open:
                # Bring existing window to front
                if self.window:
                    try:
                        self.window.lift()
                        self.window.focus_force()
                    except tk.TclError:
                        pass
                return
            self._is_open = True

        # Create window in a new thread
        thread = threading.Thread(target=self._create_window, daemon=True)
        thread.start()

    def _create_window(self) -> None:
        """Create and run the log window."""
        try:
            self.window = tk.Tk()
            self.window.title("Telegram 频道复制器 - 日志")
            self.window.geometry("800x600")

            # Configure colors
            bg_color = "#1e1e1e"
            text_color = "#d4d4d4"

            self.window.configure(bg=bg_color)

            # Create text widget with scrollbar
            self.text_widget = scrolledtext.ScrolledText(
                self.window,
                wrap=tk.WORD,
                font=("Consolas", 10),
                bg=bg_color,
                fg=text_color,
                insertbackground=text_color,
                state=tk.DISABLED,
            )
            self.text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Configure text tags for different log levels
            self.text_widget.tag_config("INFO", foreground="#4ec9b0")
            self.text_widget.tag_config("WARNING", foreground="#dcdcaa")
            self.text_widget.tag_config("ERROR", foreground="#f14c4c")
            self.text_widget.tag_config("DEBUG", foreground="#808080")

            # Clear button at bottom
            button_frame = tk.Frame(self.window, bg=bg_color)
            button_frame.pack(fill=tk.X, padx=5, pady=5)

            clear_button = tk.Button(
                button_frame,
                text="清除日志",
                command=self._clear_logs,
                bg="#333333",
                fg=text_color,
            )
            clear_button.pack(side=tk.RIGHT)

            # Handle window close
            self.window.protocol("WM_DELETE_WINDOW", self._on_close)

            # Start polling for new log messages
            self._poll_logs()

            self.window.mainloop()
        except Exception as e:
            logger.error(f"Error creating log window: {e}")
        finally:
            with self._lock:
                self._is_open = False
            self.window = None
            self.text_widget = None

    def _poll_logs(self) -> None:
        """Poll the log queue and update the text widget."""
        if not self.window or not self.text_widget:
            return

        try:
            while True:
                try:
                    log_entry = self.log_queue.get_nowait()
                    self._append_log(log_entry)
                except Empty:
                    break

            # Schedule next poll
            self.window.after(100, self._poll_logs)
        except tk.TclError:
            pass  # Window was closed

    def _append_log(self, log_entry: str) -> None:
        """Append a log entry to the text widget."""
        if not self.text_widget:
            return

        try:
            self.text_widget.config(state=tk.NORMAL)

            # Determine log level for coloring
            tag = None
            if " - INFO - " in log_entry:
                tag = "INFO"
            elif " - WARNING - " in log_entry:
                tag = "WARNING"
            elif " - ERROR - " in log_entry:
                tag = "ERROR"
            elif " - DEBUG - " in log_entry:
                tag = "DEBUG"

            self.text_widget.insert(tk.END, log_entry + "\n", tag)
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _clear_logs(self) -> None:
        """Clear all logs from the text widget."""
        if not self.text_widget:
            return

        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.config(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _on_close(self) -> None:
        """Handle window close event."""
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass

        with self._lock:
            self._is_open = False

    def add_log(self, message: str) -> None:
        """Add a log message to be displayed."""
        self.log_queue.put(message)

    def close(self) -> None:
        """Close the log window."""
        self._on_close()


class LogHandler(logging.Handler):
    """Custom logging handler that sends logs to the log window."""

    def __init__(self, log_window: LogWindow):
        super().__init__()
        self.log_window = log_window
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_window.add_log(msg)
        except Exception:
            self.handleError(record)


class TrayApp:
    """System tray application for the Telegram channel duplicator."""

    def __init__(self):
        self.icon: Optional[Icon] = None
        self.state = IconState.STOPPED

        # Duplicator components
        self.duplicator = None
        self.message_logger = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.loop_thread: Optional[threading.Thread] = None

        # Log window
        self.log_window = LogWindow()

        # Load icon images
        self._load_icons()

        # Install log handler
        self._install_log_handler()

    def _load_icons(self) -> None:
        """Load icon images for different states."""
        assets_dir = Path(__file__).parent / "assets"

        # Try to load icons, fall back to generated icons if files don't exist
        icon_files = {
            IconState.STOPPED: assets_dir / "icon_red.ico",
            IconState.RUNNING: assets_dir / "icon_green.ico",
            IconState.CONNECTING: assets_dir / "icon_yellow.ico",
        }

        self.icons = {}
        for state, icon_path in icon_files.items():
            if icon_path.exists():
                try:
                    self.icons[state] = Image.open(icon_path)
                except Exception as e:
                    logger.warning(f"Could not load icon {icon_path}: {e}")
                    self.icons[state] = self._create_fallback_icon(state)
            else:
                self.icons[state] = self._create_fallback_icon(state)

    def _create_fallback_icon(self, state: str) -> Image.Image:
        """Create a simple fallback icon if the icon file is missing."""
        colors = {
            IconState.STOPPED: (255, 0, 0),
            IconState.RUNNING: (0, 255, 0),
            IconState.CONNECTING: (255, 255, 0),
        }
        color = colors.get(state, (128, 128, 128))

        # Create a simple 64x64 colored square
        img = Image.new("RGB", (64, 64), color)
        return img

    def _install_log_handler(self) -> None:
        """Install log handler to capture logs for the log window."""
        handler = LogHandler(self.log_window)
        handler.setLevel(logging.DEBUG)

        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        # Also add to specific loggers
        for logger_name in ["__main__", "installer", "src"]:
            logging.getLogger(logger_name).addHandler(handler)

    def _get_icon(self) -> Image.Image:
        """Get the current icon based on state."""
        return self.icons.get(self.state, self.icons[IconState.STOPPED])

    def _create_menu(self) -> Menu:
        """Create the right-click menu."""
        return Menu(
            # Default item for double-click - hidden but triggers toggle
            MenuItem(
                "切换",
                self._on_double_click,
                default=True,
                visible=False,
            ),
            MenuItem(
                "启动",
                self._on_start,
                visible=lambda item: self.state == IconState.STOPPED,
            ),
            MenuItem(
                "停止",
                self._on_stop,
                visible=lambda item: self.state != IconState.STOPPED,
            ),
            Menu.SEPARATOR,
            MenuItem("编辑配置", self._on_edit_config),
            MenuItem("查看日志", self._on_view_logs),
            MenuItem("重新设置", self._on_rerun_wizard),
            Menu.SEPARATOR,
            MenuItem("退出", self._on_exit),
        )

    def _update_icon(self) -> None:
        """Update the tray icon based on current state."""
        if self.icon:
            self.icon.icon = self._get_icon()
            # Update menu to reflect state changes
            self.icon.menu = self._create_menu()

    def _show_notification(self, title: str, message: str) -> None:
        """Show a Windows notification."""
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception as e:
                logger.warning(f"Could not show notification: {e}")

    def _on_start(self, icon=None, item=None) -> None:
        """Start the duplicator."""
        if self.state != IconState.STOPPED:
            return

        # Check if config exists
        config_status = config_exists()
        if not config_status["env"] or not config_status["config"]:
            self._show_notification(
                "配置缺失",
                "请先完成配置向导。正在打开向导...",
            )
            self._on_rerun_wizard()
            return

        logger.info("Starting duplicator...")
        self.state = IconState.CONNECTING
        self._update_icon()
        self._show_notification("连接中", "正在连接 Telegram...")

        # Start in background thread
        thread = threading.Thread(target=self._start_duplicator, daemon=True)
        thread.start()

    def _start_duplicator(self) -> None:
        """Start the duplicator in a background thread."""
        try:
            # Import here to avoid loading Telethon on startup
            # Handle both bundled and development modes
            try:
                from src.config import Config
                from src.duplicator import ChannelDuplicator
            except ImportError:
                # When bundled, src is at top level
                from config import Config
                from duplicator import ChannelDuplicator

            # Change to project root for session files
            os.chdir(PROJECT_ROOT)

            # Create new event loop for this thread
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)

            # Load config and create duplicator
            config = Config()
            self.duplicator = ChannelDuplicator(config)

            # Run the startup
            self.event_loop.run_until_complete(self._async_start())

        except Exception as e:
            logger.error(f"Failed to start duplicator: {e}")
            self.state = IconState.STOPPED
            self._update_icon()
            self._show_notification("启动失败", str(e))
            return

        # Run until stopped
        try:
            self.event_loop.run_until_complete(
                self.duplicator.client.run_until_disconnected()
            )
        except Exception as e:
            if self.state != IconState.STOPPED:  # Not a manual stop
                logger.error(f"Duplicator disconnected: {e}")
                self._show_notification("已断开", str(e))
        finally:
            self.state = IconState.STOPPED
            self._update_icon()
            self._cleanup()

    async def _async_start(self) -> None:
        """Async startup routine."""
        await self.duplicator.start()

        # Optionally attach message logger
        try:
            try:
                from message_logger import create_message_logger
            except ImportError:
                from installer.message_logger import create_message_logger
            self.message_logger = create_message_logger(
                self.duplicator.client,
                auto_start=True,
            )
            if self.message_logger:
                logger.info("Message logger attached")
        except Exception as e:
            logger.warning(f"Message logger not available: {e}")

        # Update state to running
        self.state = IconState.RUNNING
        self._update_icon()
        self._show_notification("已启动", "频道复制器正在运行")
        logger.info("Duplicator is now running")

    def _on_stop(self, icon=None, item=None) -> None:
        """Stop the duplicator."""
        if self.state == IconState.STOPPED:
            return

        logger.info("Stopping duplicator...")
        self.state = IconState.STOPPED
        self._update_icon()

        # Stop in background
        thread = threading.Thread(target=self._stop_duplicator, daemon=True)
        thread.start()

    def _stop_duplicator(self) -> None:
        """Stop the duplicator in a background thread."""
        try:
            # Stop message logger first
            if self.message_logger:
                self.message_logger.stop()
                self.message_logger = None

            # Stop duplicator
            if self.duplicator and self.event_loop:
                future = asyncio.run_coroutine_threadsafe(
                    self.duplicator.stop(),
                    self.event_loop,
                )
                future.result(timeout=10)

            self._cleanup()
            self._show_notification("已停止", "频道复制器已停止")
            logger.info("Duplicator stopped")

        except Exception as e:
            logger.error(f"Error stopping duplicator: {e}")

    def _cleanup(self) -> None:
        """Clean up resources."""
        self.duplicator = None

        if self.event_loop:
            try:
                self.event_loop.stop()
            except Exception:
                pass
            self.event_loop = None

    def _on_edit_config(self, icon=None, item=None) -> None:
        """Open config.yaml in the default editor (notepad on Windows)."""
        logger.info("Opening config file...")

        if not CONFIG_FILE.exists():
            self._show_notification(
                "配置不存在",
                "config.yaml 不存在，请先运行配置向导",
            )
            return

        try:
            if sys.platform == "win32":
                # Use notepad on Windows
                subprocess.Popen(["notepad.exe", str(CONFIG_FILE)])
            elif sys.platform == "darwin":
                # Use open on macOS
                subprocess.Popen(["open", "-e", str(CONFIG_FILE)])
            else:
                # Try xdg-open on Linux
                subprocess.Popen(["xdg-open", str(CONFIG_FILE)])
        except Exception as e:
            logger.error(f"Could not open config file: {e}")
            self._show_notification("错误", f"无法打开配置文件: {e}")

    def _on_view_logs(self, icon=None, item=None) -> None:
        """Open the log viewer window."""
        logger.info("Opening log window...")
        self.log_window.open()

    def _on_rerun_wizard(self, icon=None, item=None) -> None:
        """Re-run the setup wizard."""
        logger.info("Launching setup wizard...")

        # Stop duplicator first if running
        if self.state != IconState.STOPPED:
            self._on_stop()

        try:
            wizard_path = Path(__file__).parent / "setup_wizard.py"
            if wizard_path.exists():
                subprocess.Popen(
                    [sys.executable, str(wizard_path)],
                    cwd=str(PROJECT_ROOT),
                )
            else:
                logger.error("Setup wizard not found")
                self._show_notification("错误", "找不到安装向导")
        except Exception as e:
            logger.error(f"Could not launch wizard: {e}")
            self._show_notification("错误", f"无法启动向导: {e}")

    def _on_exit(self, icon=None, item=None) -> None:
        """Exit the application."""
        logger.info("Exiting...")

        # Stop duplicator
        if self.state != IconState.STOPPED:
            self._stop_duplicator()

        # Close log window
        self.log_window.close()

        # Stop the icon
        if self.icon:
            self.icon.stop()

    def _on_double_click(self, icon=None, item=None) -> None:
        """Handle double-click on tray icon (toggle start/stop)."""
        if self.state == IconState.STOPPED:
            self._on_start()
        else:
            self._on_stop()

    def _setup_icon(self, icon: Icon) -> None:
        """Setup callback for the icon (called when icon is ready)."""
        # Make the icon visible
        icon.visible = True

    def run(self) -> None:
        """Run the tray application."""
        # Check config on startup
        config_status = config_exists()
        if not config_status["env"] or not config_status["config"]:
            logger.info("Configuration missing, launching setup wizard...")
            self._on_rerun_wizard()

        # Create the tray icon
        self.icon = Icon(
            "Telegram Channel Duplicator",
            self._get_icon(),
            "Telegram 频道复制器",
            menu=self._create_menu(),
        )

        # Set up double-click handler using default menu item
        # pystray calls the default menu item on double-click (Windows)
        # We add a hidden default item that toggles start/stop
        self.icon.run(setup=self._setup_icon)


def main() -> None:
    """Main entry point."""
    # Change to project root
    os.chdir(PROJECT_ROOT)

    logger.info("Starting Telegram Channel Duplicator Tray App...")

    app = TrayApp()
    app.run()


if __name__ == "__main__":
    main()
