"""
Setup Wizard for Telegram Channel Duplicator

A 4-step Tkinter wizard (in Chinese) for initial configuration:
1. Welcome screen
2. Telegram API setup
3. Channel configuration
4. Completion and launch

Usage:
    python installer/setup_wizard.py
"""

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

# Determine if we're running as a bundled executable or as a script
if getattr(sys, 'frozen', False):
    # Running as bundled executable (PyInstaller)
    BUNDLE_DIR = Path(sys._MEIPASS)
    sys.path.insert(0, str(BUNDLE_DIR))
    sys.path.insert(0, str(BUNDLE_DIR / 'installer'))
else:
    # Running as script
    sys.path.insert(0, str(Path(__file__).parent.parent))
    sys.path.insert(0, str(Path(__file__).parent))

# Import config_manager - handle both bundled and development modes
try:
    from config_manager import save_config, save_env
except ImportError:
    from installer.config_manager import save_config, save_env


class SetupWizard:
    """4-step setup wizard for Telegram Channel Duplicator configuration."""

    # UI Constants
    WINDOW_WIDTH = 600
    WINDOW_HEIGHT = 500
    PADDING = 20
    BUTTON_WIDTH = 12

    # Colors for a clean look
    BG_COLOR = "#f5f5f5"
    ACCENT_COLOR = "#0088cc"
    TEXT_COLOR = "#333333"
    LIGHT_TEXT = "#666666"

    def __init__(self, root: tk.Tk):
        """Initialize the setup wizard.

        Args:
            root: Tkinter root window
        """
        self.root = root
        self.current_step = 0

        # Data storage
        self.api_id = tk.StringVar()
        self.api_hash = tk.StringVar()
        self.target_channel = tk.StringVar()
        self.my_channel_name = tk.StringVar()
        self.my_username = tk.StringVar()
        self.my_contact_username = tk.StringVar()
        self.source_channels_text = None  # Will be Text widget

        self._setup_window()
        self._create_main_container()
        self._create_steps()
        self._show_step(0)

    def _setup_window(self) -> None:
        """Configure the main window."""
        self.root.title("Telegram 频道复制器 - 安装向导")
        self.root.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG_COLOR)

        # Center window on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.WINDOW_WIDTH) // 2
        y = (self.root.winfo_screenheight() - self.WINDOW_HEIGHT) // 2
        self.root.geometry(f"+{x}+{y}")

    def _create_main_container(self) -> None:
        """Create the main container with header and content area."""
        # Header frame with step indicator
        self.header_frame = tk.Frame(self.root, bg=self.ACCENT_COLOR, height=60)
        self.header_frame.pack(fill=tk.X)
        self.header_frame.pack_propagate(False)

        self.header_label = tk.Label(
            self.header_frame,
            text="",
            font=("Microsoft YaHei UI", 14, "bold"),
            fg="white",
            bg=self.ACCENT_COLOR,
        )
        self.header_label.pack(expand=True)

        # Step indicator
        self.step_indicator_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        self.step_indicator_frame.pack(fill=tk.X, pady=(15, 5))

        self.step_labels = []
        step_names = ["欢迎", "API 设置", "频道配置", "完成"]
        for i, name in enumerate(step_names):
            label = tk.Label(
                self.step_indicator_frame,
                text=f"{i + 1}. {name}",
                font=("Microsoft YaHei UI", 9),
                fg=self.LIGHT_TEXT,
                bg=self.BG_COLOR,
            )
            label.pack(side=tk.LEFT, expand=True)
            self.step_labels.append(label)

        # Navigation frame at bottom (pack FIRST so it gets space before content expands)
        self.nav_frame = tk.Frame(self.root, bg=self.BG_COLOR, pady=15)
        self.nav_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.back_button = ttk.Button(
            self.nav_frame,
            text="上一步",
            width=self.BUTTON_WIDTH,
            command=self._go_back,
        )
        self.back_button.pack(side=tk.LEFT, padx=self.PADDING)

        self.next_button = ttk.Button(
            self.nav_frame,
            text="下一步",
            width=self.BUTTON_WIDTH,
            command=self._go_next,
        )
        self.next_button.pack(side=tk.RIGHT, padx=self.PADDING)

        # Content frame (will hold step frames) - pack AFTER nav_frame
        self.content_frame = tk.Frame(
            self.root, bg=self.BG_COLOR, padx=self.PADDING, pady=self.PADDING
        )
        self.content_frame.pack(fill=tk.BOTH, expand=True)

    def _create_steps(self) -> None:
        """Create all step frames."""
        self.steps = [
            self._create_step_welcome(),
            self._create_step_api(),
            self._create_step_channels(),
            self._create_step_complete(),
        ]

    def _create_step_welcome(self) -> tk.Frame:
        """Create Step 1: Welcome screen."""
        frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)

        # Welcome title
        title = tk.Label(
            frame,
            text="欢迎使用 Telegram 频道复制器",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
        )
        title.pack(pady=(20, 30))

        # Description
        desc_text = """此向导将帮助您完成 Telegram 频道复制器的初始配置。

您将需要：
  1. Telegram API 凭证 (API_ID 和 API_HASH)
     可从 my.telegram.org 获取

  2. 您的目标频道信息
     用于接收复制的消息

  3. 来源频道列表
     您想要监控并复制的频道

配置完成后，程序将在系统托盘中运行，
自动监控来源频道并将消息复制到您的目标频道。

点击"下一步"开始配置。"""

        desc = tk.Label(
            frame,
            text=desc_text,
            font=("Microsoft YaHei UI", 11),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
            justify=tk.LEFT,
            anchor="w",
        )
        desc.pack(fill=tk.X, padx=20)

        return frame

    def _create_step_api(self) -> tk.Frame:
        """Create Step 2: Telegram API setup."""
        frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)

        # Instructions
        instructions = tk.Label(
            frame,
            text="从 my.telegram.org 获取您的 API 凭证",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
        )
        instructions.pack(pady=(10, 5))

        guide_text = """步骤：
1. 点击下方按钮打开 my.telegram.org
2. 登录您的 Telegram 账号
3. 点击 "API development tools"
4. 创建一个新应用（应用名称随意）
5. 复制 API_ID 和 API_HASH 到下方"""

        guide = tk.Label(
            frame,
            text=guide_text,
            font=("Microsoft YaHei UI", 10),
            fg=self.LIGHT_TEXT,
            bg=self.BG_COLOR,
            justify=tk.LEFT,
        )
        guide.pack(pady=(0, 15))

        # Open browser button
        open_btn = ttk.Button(
            frame,
            text="打开浏览器 (my.telegram.org)",
            command=self._open_telegram_website,
        )
        open_btn.pack(pady=(0, 25))

        # API ID input
        self._create_labeled_entry(
            frame,
            "API_ID:",
            self.api_id,
            "纯数字，例如: 12345678",
        )

        # API Hash input
        self._create_labeled_entry(
            frame,
            "API_HASH:",
            self.api_hash,
            "32位字符，例如: abcdef1234567890abcdef1234567890",
        )

        return frame

    def _create_step_channels(self) -> tk.Frame:
        """Create Step 3: Channel configuration."""
        frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)

        # Instructions
        instructions = tk.Label(
            frame,
            text="配置频道信息",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
        )
        instructions.pack(pady=(5, 10))

        # Scrollable content
        canvas = tk.Canvas(frame, bg=self.BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.BG_COLOR)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Target channel input
        self._create_labeled_entry(
            scrollable_frame,
            "目标频道 (target_channel):",
            self.target_channel,
            "例如: @mychannel 或 -1001234567890",
            required=True,
        )

        # Channel name input
        self._create_labeled_entry(
            scrollable_frame,
            "频道名称 (my_channel_name):",
            self.my_channel_name,
            "显示名称，用于文字替换",
        )

        # Username input
        self._create_labeled_entry(
            scrollable_frame,
            "频道用户名 (my_username):",
            self.my_username,
            "例如: @mychannel",
        )

        # Contact username input
        self._create_labeled_entry(
            scrollable_frame,
            "联系用户名 (my_contact_username):",
            self.my_contact_username,
            "例如: @mycontact",
        )

        # Source channels (multiline)
        source_label = tk.Label(
            scrollable_frame,
            text="来源频道 (source_channels):",
            font=("Microsoft YaHei UI", 10, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
            anchor="w",
        )
        source_label.pack(fill=tk.X, pady=(15, 2))

        source_hint = tk.Label(
            scrollable_frame,
            text="每行一个频道，例如: @channel1 或 -1001234567890",
            font=("Microsoft YaHei UI", 9),
            fg=self.LIGHT_TEXT,
            bg=self.BG_COLOR,
            anchor="w",
        )
        source_hint.pack(fill=tk.X)

        # Text widget for multiline input
        text_frame = tk.Frame(scrollable_frame, bg=self.BG_COLOR)
        text_frame.pack(fill=tk.X, pady=(5, 10))

        self.source_channels_text = tk.Text(
            text_frame,
            height=5,
            font=("Consolas", 10),
            wrap=tk.NONE,
        )
        self.source_channels_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        text_scrollbar = ttk.Scrollbar(
            text_frame, orient="vertical", command=self.source_channels_text.yview
        )
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.source_channels_text.configure(yscrollcommand=text_scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        return frame

    def _create_step_complete(self) -> tk.Frame:
        """Create Step 4: Completion screen."""
        frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)

        # Title
        title = tk.Label(
            frame,
            text="配置完成",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
        )
        title.pack(pady=(20, 20))

        # Summary label
        summary_label = tk.Label(
            frame,
            text="配置摘要:",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
            anchor="w",
        )
        summary_label.pack(fill=tk.X, padx=20)

        # Summary text (will be updated when step is shown)
        self.summary_text = tk.Text(
            frame,
            height=12,
            font=("Consolas", 10),
            bg="white",
            state=tk.DISABLED,
            wrap=tk.WORD,
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))

        # Info label
        info = tk.Label(
            frame,
            text='点击"完成并启动"将保存配置并启动托盘应用',
            font=("Microsoft YaHei UI", 10),
            fg=self.LIGHT_TEXT,
            bg=self.BG_COLOR,
        )
        info.pack()

        return frame

    def _create_labeled_entry(
        self,
        parent: tk.Frame,
        label_text: str,
        variable: tk.StringVar,
        hint: str = "",
        required: bool = False,
    ) -> ttk.Entry:
        """Create a labeled entry field.

        Args:
            parent: Parent frame
            label_text: Label text
            variable: StringVar for the entry
            hint: Hint text below the entry
            required: Whether to show required indicator

        Returns:
            The created Entry widget
        """
        label_full = label_text
        if required:
            label_full = label_text + " *"

        label = tk.Label(
            parent,
            text=label_full,
            font=("Microsoft YaHei UI", 10, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
            anchor="w",
        )
        label.pack(fill=tk.X, pady=(10, 2))

        entry = ttk.Entry(parent, textvariable=variable, font=("Consolas", 10))
        entry.pack(fill=tk.X, pady=(0, 2))

        if hint:
            hint_label = tk.Label(
                parent,
                text=hint,
                font=("Microsoft YaHei UI", 9),
                fg=self.LIGHT_TEXT,
                bg=self.BG_COLOR,
                anchor="w",
            )
            hint_label.pack(fill=tk.X)

        return entry

    def _show_step(self, step_num: int) -> None:
        """Show a specific step.

        Args:
            step_num: Step number (0-3)
        """
        # Hide all steps
        for step in self.steps:
            step.pack_forget()

        # Show current step
        self.steps[step_num].pack(fill=tk.BOTH, expand=True)
        self.current_step = step_num

        # Update header
        headers = [
            "第一步: 欢迎",
            "第二步: Telegram API 设置",
            "第三步: 频道配置",
            "第四步: 完成",
        ]
        self.header_label.config(text=headers[step_num])

        # Update step indicator
        for i, label in enumerate(self.step_labels):
            if i < step_num:
                label.config(fg="#00aa00")  # Completed - green
            elif i == step_num:
                label.config(fg=self.ACCENT_COLOR, font=("Microsoft YaHei UI", 9, "bold"))
            else:
                label.config(fg=self.LIGHT_TEXT, font=("Microsoft YaHei UI", 9))

        # Update navigation buttons
        self.back_button.config(state=tk.NORMAL if step_num > 0 else tk.DISABLED)

        if step_num == 3:  # Final step
            self.next_button.config(text="完成并启动")
            self._update_summary()
        else:
            self.next_button.config(text="下一步")

    def _update_summary(self) -> None:
        """Update the summary text on the final step."""
        sources = self._get_source_channels()

        summary = f"""API_ID: {self.api_id.get() or '(未设置)'}
API_HASH: {self.api_hash.get()[:8] + '...' if self.api_hash.get() else '(未设置)'}

目标频道: {self.target_channel.get() or '(未设置)'}
频道名称: {self.my_channel_name.get() or '(未设置)'}
频道用户名: {self.my_username.get() or '(未设置)'}
联系用户名: {self.my_contact_username.get() or '(未设置)'}

来源频道 ({len(sources)} 个):
"""
        for source in sources[:5]:  # Show first 5
            summary += f"  - {source}\n"
        if len(sources) > 5:
            summary += f"  ... 还有 {len(sources) - 5} 个频道\n"
        if not sources:
            summary += "  (未设置)\n"

        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, summary)
        self.summary_text.config(state=tk.DISABLED)

    def _get_source_channels(self) -> list:
        """Get source channels from text widget.

        Returns:
            List of source channel strings
        """
        if self.source_channels_text is None:
            return []
        text = self.source_channels_text.get("1.0", tk.END)
        lines = [line.strip() for line in text.split("\n")]
        return [line for line in lines if line]  # Remove empty lines

    def _go_back(self) -> None:
        """Go to the previous step."""
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _go_next(self) -> None:
        """Go to the next step or finish."""
        # Validate current step
        if not self._validate_current_step():
            return

        if self.current_step < 3:
            self._show_step(self.current_step + 1)
        else:
            self._finish()

    def _validate_current_step(self) -> bool:
        """Validate the current step's inputs.

        Returns:
            True if validation passes, False otherwise
        """
        if self.current_step == 1:  # API setup
            return self._validate_api_step()
        elif self.current_step == 2:  # Channel config
            return self._validate_channel_step()
        return True

    def _validate_api_step(self) -> bool:
        """Validate API configuration step.

        Returns:
            True if validation passes
        """
        api_id = self.api_id.get().strip()
        api_hash = self.api_hash.get().strip()

        if not api_id:
            messagebox.showerror("验证错误", "请输入 API_ID")
            return False

        if not api_id.isdigit():
            messagebox.showerror("验证错误", "API_ID 必须为纯数字")
            return False

        if not api_hash:
            messagebox.showerror("验证错误", "请输入 API_HASH")
            return False

        return True

    def _validate_channel_step(self) -> bool:
        """Validate channel configuration step.

        Returns:
            True if validation passes
        """
        target = self.target_channel.get().strip()
        sources = self._get_source_channels()

        if not target:
            messagebox.showerror("验证错误", "请输入目标频道")
            return False

        if not sources:
            messagebox.showerror("验证错误", "请至少输入一个来源频道")
            return False

        return True

    def _open_telegram_website(self) -> None:
        """Open my.telegram.org in the default browser."""
        import webbrowser

        webbrowser.open("https://my.telegram.org")

    def _finish(self) -> None:
        """Save configuration and launch the tray application."""
        try:
            # Save .env file
            save_env(
                api_id=self.api_id.get().strip(),
                api_hash=self.api_hash.get().strip(),
            )

            # Save config.yaml
            save_config(
                target=self.target_channel.get().strip(),
                name=self.my_channel_name.get().strip(),
                username=self.my_username.get().strip(),
                contact=self.my_contact_username.get().strip(),
                sources=self._get_source_channels(),
            )

            messagebox.showinfo(
                "配置成功",
                "配置已保存！\n\n"
                ".env 和 config.yaml 已创建。\n"
                "正在启动托盘应用...",
            )

            # Launch tray application
            self._launch_tray_app()

            # Close wizard
            self.root.destroy()

        except Exception as e:
            messagebox.showerror("保存失败", f"保存配置时出错:\n{e}")

    def _launch_tray_app(self) -> None:
        """Launch the tray application."""
        try:
            # Get the project root
            project_root = Path(__file__).parent.parent

            # Try to find and launch tray_app.py
            tray_app = project_root / "tray_app.py"
            if tray_app.exists():
                subprocess.Popen(
                    [sys.executable, str(tray_app)],
                    cwd=str(project_root),
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32"
                    else 0,
                )
            else:
                # Try tray_app.pyw for Windows
                tray_pyw = project_root / "tray_app.pyw"
                if tray_pyw.exists():
                    subprocess.Popen(
                        [sys.executable, str(tray_pyw)],
                        cwd=str(project_root),
                        creationflags=subprocess.CREATE_NO_WINDOW
                        if sys.platform == "win32"
                        else 0,
                    )
        except Exception as e:
            # Don't fail if tray app can't be launched
            print(f"Warning: Could not launch tray app: {e}")


def main() -> None:
    """Main entry point for the setup wizard."""
    root = tk.Tk()

    # Apply a theme style
    style = ttk.Style()
    try:
        # Use a more modern theme if available
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except tk.TclError:
        pass  # Use default theme

    SetupWizard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
