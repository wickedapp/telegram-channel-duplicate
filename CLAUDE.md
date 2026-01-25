# Telegram Channel Duplicator

## Project Structure
- `src/` - Core duplicator logic (config, filters, transformer, duplicator)
- `installer/` - Windows installer components (tray app, setup wizard, build scripts)

## Build Commands
- `python installer/build_installer.py` - Build Windows executable (runs PyArmor + PyInstaller)
- `zip -r windows_build_files.zip installer/ src/ requirements.txt config.yaml.template .env.template -x "*.pyc" -x "*__pycache__*"` - Create deployment zip

## PyInstaller Bundling Gotchas
- tkinter submodules need explicit hidden imports: `tkinter.simpledialog`, `tkinter.messagebox`, `tkinter.scrolledtext`
- Add `tkinter` to `--collect-all` for complete bundling
- PyArmor 9.x uses `pyarmor` command directly, not `python -m pyarmor`
- When bundled (`sys.frozen`), use `Path(sys.executable).parent` for config paths, not `__file__`
- Use PyMySQL instead of mysql-connector-python (pure Python, no C extension DLLs to bundle)

## Silent Logging Pattern
```python
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.propagate = False
```
Use this to completely hide a module's logs from users.

## Config Defaults
- When adding default behaviors, update both `config.yaml.template` AND `installer/config_manager.py`

## GUI Mode Detection
```python
def is_gui_mode() -> bool:
    return getattr(sys, 'frozen', False) or not sys.stdin or not sys.stdin.isatty()
```
Use this pattern when app runs with `--noconsole` to show tkinter dialogs instead of console input.

## Testing
- Test bundled exe on clean Windows machine (no Python installed)
- First run triggers Telegram auth dialogs (phone, code, 2FA password)
- Session file saves to exe directory after successful auth
