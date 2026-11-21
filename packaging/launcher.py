"""Entry point of the one-click Edgeware.exe (PyInstaller build).

Edgeware starts its own parts (main program, config window, mpv helper, panic) with
`subprocess.Popen([sys.executable, some_script.py, ...])`. In a frozen build `sys.executable`
is Edgeware.exe itself, so this launcher makes the exe behave like a tiny Python interpreter:

    Edgeware.exe                       -> opens the config window (what a double-click should do)
    Edgeware.exe <script.py|.pyw> ...  -> runs that script, exactly like `python script.py ...`

The scripts stay plain files in the `app` folder next to the exe (so packs, config, logs and the
built-in updater keep working); only Python and the third-party libraries are frozen into the exe.
"""

import os
import runpy
import sys
import traceback
from pathlib import Path

APP_DIR = Path(sys.executable).resolve().parent / "app" if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent / "edgeware"


def fail(message: str) -> None:
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("Edgeware++", message, parent=root)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)
    sys.exit(1)


def run_script(script: Path, args: list[str]) -> None:
    if not script.is_file():
        fail(f"Edgeware could not find this file:\n{script}\n\nKeep the 'app' folder next to Edgeware.exe.")
    # Like the real interpreter: the script's folder is searched first, then the app folder.
    for folder in (APP_DIR, script.parent):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    os.chdir(script.parent)
    sys.argv = [str(script), *args]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit:
        raise
    except Exception as error:
        log = APP_DIR / "data" / "logs" / "launcher_crash.txt"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        fail(f"{type(error).__name__}: {error}\n\nDetails: {log}")


def main() -> None:
    import multiprocessing

    multiprocessing.freeze_support()
    args = sys.argv[1:]
    shortcuts = {"--config": "config.pyw", "--edgeware": "edgeware.pyw", "--panic": "panic.pyw"}

    if args and args[0].lower().endswith((".py", ".pyw")):
        run_script(Path(args[0]).resolve(), args[1:])
    elif args and args[0] in shortcuts:
        run_script(APP_DIR / shortcuts[args[0]], args[1:])
    elif args and args[0] == "-c":
        exec(args[1], {"__name__": "__main__"})  # noqa: S102 - same as `python -c`, used by helper scripts
    else:
        run_script(APP_DIR / "config.pyw", args)


if __name__ == "__main__":
    main()
