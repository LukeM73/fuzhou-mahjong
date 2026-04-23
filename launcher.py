"""
Fuzhou Mahjong — Desktop Launcher
==================================
A simple GUI launcher so players can start the game without a terminal.
Presents three options:
  • Solo Play  — local game vs AI
  • Host Game  — start the WebSocket server, then open the client
  • Join Game  — connect to a friend's server

Auto-updater
------------
On startup a background thread queries the GitHub Releases API.  If a newer
version is available an update banner appears in the launcher.  Clicking
"Update Now" downloads the zip, extracts it to a temp folder, writes a small
batch script that swaps the files after the app exits, then closes the app.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import urllib.request
import zipfile
from pathlib import Path
from tkinter import messagebox
from typing import Optional

from version import __version__

# ------------------------------------------------------------------ config

GITHUB_OWNER = "LukeM73"
GITHUB_REPO  = "fuzhou-mahjong"
# Asset that GitHub Actions attaches to every release:
RELEASE_ASSET_NAME = "FuzhouMahjong.zip"

RELEASES_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)

# ------------------------------------------------------------------ helpers

def _python() -> str:
    """Return the current Python executable (works inside PyInstaller too)."""
    return sys.executable


def _app_dir() -> Path:
    """Directory that contains the running .exe (or launcher.py in dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def _run_module(module: str, *extra_args: str) -> subprocess.Popen:
    """Spawn a detached subprocess running `python -m <module> [args]`."""
    cmd = [_python(), "-m", module, *extra_args]
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(cmd, **kwargs)


def _parse_version(tag: str) -> tuple[int, ...]:
    """'v1.2.3' → (1, 2, 3).  Returns (0,) on parse failure."""
    try:
        return tuple(int(x) for x in tag.lstrip("v").split("."))
    except Exception:
        return (0,)


# ------------------------------------------------------------------ updater

class Updater:
    """
    Runs entirely in background threads.  Calls back onto the Tk main thread
    via `root.after(0, …)` so it is thread-safe.
    """

    def __init__(self, root: tk.Tk, on_update_available):
        self._root = root
        self._on_available = on_update_available
        self._download_url: Optional[str] = None
        self._latest_tag: str = ""

    # ── public ──────────────────────────────────────────────────────────

    def check_async(self):
        """Start the background version-check.  Returns immediately."""
        threading.Thread(target=self._check, daemon=True).start()

    def download_and_install(self, progress_cb=None):
        """Download the release zip and schedule the swap on exit."""
        threading.Thread(
            target=self._download, args=(progress_cb,), daemon=True
        ).start()

    # ── internals ───────────────────────────────────────────────────────

    def _check(self):
        try:
            req = urllib.request.Request(
                RELEASES_API,
                headers={"User-Agent": f"FuzhouMahjong/{__version__}"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            tag = data.get("tag_name", "")
            if _parse_version(tag) > _parse_version(__version__):
                # Find the zip asset URL
                for asset in data.get("assets", []):
                    if asset["name"] == RELEASE_ASSET_NAME:
                        self._download_url = asset["browser_download_url"]
                        break
                self._latest_tag = tag
                self._root.after(0, lambda: self._on_available(tag))
        except Exception:
            pass  # silently ignore network errors on startup

    def _download(self, progress_cb=None):
        if not self._download_url:
            return

        tmp_dir   = Path(tempfile.mkdtemp(prefix="fzm_update_"))
        zip_path  = tmp_dir / RELEASE_ASSET_NAME
        extract   = tmp_dir / "extracted"

        try:
            # ── download ────────────────────────────────────────────────
            req = urllib.request.Request(
                self._download_url,
                headers={"User-Agent": f"FuzhouMahjong/{__version__}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk = 65536
                with open(zip_path, "wb") as fh:
                    while True:
                        buf = resp.read(chunk)
                        if not buf:
                            break
                        fh.write(buf)
                        downloaded += len(buf)
                        if progress_cb and total:
                            progress_cb(downloaded / total)

            # ── extract ─────────────────────────────────────────────────
            extract.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract)

            # The zip contains a single top-level folder: FuzhouMahjong/
            new_app = extract / "FuzhouMahjong"
            if not new_app.exists():
                # Fallback: treat extracted root as the new app
                new_app = extract

            # ── write the swap script ────────────────────────────────────
            install_dir = str(_app_dir())
            bat_path    = tmp_dir / "_apply_update.bat"
            exe_path    = str(_app_dir() / "FuzhouMahjong.exe")

            bat_content = f"""@echo off
REM Fuzhou Mahjong auto-update swap script — generated automatically
timeout /t 2 /nobreak >nul
robocopy "{new_app}" "{install_dir}" /E /IS /IT /NFL /NDL /NJH /NJS >nul
start "" "{exe_path}"
rd /s /q "{tmp_dir}"
del "%~f0"
"""
            bat_path.write_text(bat_content, encoding="utf-8")

            # ── launch swap script and exit ──────────────────────────────
            subprocess.Popen(
                ["cmd", "/c", str(bat_path)],
                creationflags=subprocess.CREATE_NO_WINDOW
                | subprocess.DETACHED_PROCESS,
                close_fds=True,
            )

            self._root.after(0, self._root.destroy)

        except Exception as exc:
            self._root.after(
                0,
                lambda: messagebox.showerror(
                    "Update failed",
                    f"Could not complete the update:\n{exc}\n\n"
                    "You can download it manually from:\n"
                    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases",
                ),
            )
            # Clean up on failure
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ------------------------------------------------------------------ UI

BG          = "#0e3c26"   # dark green felt
PANEL       = "#164d30"   # slightly lighter panel
ACCENT      = "#daa832"   # gold
ACCENT_DARK = "#a07820"
UPDATE_BG   = "#1a5c3a"   # slightly lighter strip for the update banner
TEXT        = "#f8eed4"   # ivory
BTN_FG      = "#1a1a0a"
FONT_TITLE  = ("Georgia", 28, "bold")
FONT_SUB    = ("Georgia", 12, "italic")
FONT_BTN    = ("Segoe UI", 13, "bold")
FONT_LABEL  = ("Segoe UI", 10)
FONT_ENTRY  = ("Consolas", 11)
FONT_SMALL  = ("Segoe UI", 8)


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fuzhou Mahjong")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._server_proc: Optional[subprocess.Popen] = None
        self._update_frame: Optional[tk.Frame] = None
        self._progress_var = tk.DoubleVar(value=0)
        self._build_ui()
        self._center()

        # Kick off update check after the window is shown
        self._updater = Updater(self, self._on_update_available)
        self.after(500, self._updater.check_async)

    # ---------------------------------------------------------------- layout

    def _build_ui(self):
        # ── title block ──────────────────────────────────────────────────
        tk.Label(self, text="福州麻将", font=("Georgia", 36, "bold"),
                 fg=ACCENT, bg=BG).pack(pady=(30, 0))
        tk.Label(self, text="Fuzhou Mahjong", font=FONT_TITLE,
                 fg=TEXT, bg=BG).pack(pady=(2, 0))
        tk.Label(self, text="16-tile · Gold Tile wildcard · Online with friends",
                 font=FONT_SUB, fg=ACCENT, bg=BG).pack(pady=(4, 24))

        # ── divider ──────────────────────────────────────────────────────
        tk.Frame(self, bg=ACCENT, height=1, width=360).pack(pady=(0, 24))

        # ── main buttons ─────────────────────────────────────────────────
        self._btn(
            "🀄  Solo Play",
            "Play against AI — no internet needed",
            self._solo,
        ).pack(pady=6)

        self._btn(
            "🌐  Host a Game",
            "Start a server so friends can join you",
            self._host,
        ).pack(pady=6)

        # ── join block ───────────────────────────────────────────────────
        join_frame = tk.Frame(self, bg=BG)
        join_frame.pack(pady=6)

        self._btn(
            "🔗  Join a Game",
            "Connect to a friend's server",
            self._join,
            parent=join_frame,
        ).grid(row=0, column=0, padx=(0, 8))

        entry_frame = tk.Frame(join_frame, bg=PANEL, bd=0,
                               highlightbackground=ACCENT,
                               highlightthickness=1)
        entry_frame.grid(row=0, column=1)

        self._host_var = tk.StringVar(value=self._PLACEHOLDER)
        self._host_entry = tk.Entry(
            entry_frame,
            textvariable=self._host_var,
            font=FONT_ENTRY,
            width=18,
            bg=PANEL,
            fg="#5a8a6a",
            insertbackground=ACCENT,
            relief="flat",
            bd=6,
        )
        self._host_entry.pack()
        self._host_entry.bind("<FocusIn>",  self._entry_focus_in)
        self._host_entry.bind("<FocusOut>", self._entry_focus_out)

        # ── status label ─────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var,
                 font=FONT_LABEL, fg=ACCENT, bg=BG).pack(pady=(16, 0))

        # ── footer ───────────────────────────────────────────────────────
        tk.Frame(self, bg=ACCENT, height=1, width=360).pack(pady=(20, 8))
        tk.Label(self, text=f"v{__version__}  ·  Python + Pygame",
                 font=FONT_SMALL, fg="#5a8a6a", bg=BG).pack(pady=(0, 16))

    def _btn(self, label: str, tooltip: str, cmd,
             parent=None) -> tk.Button:
        if parent is None:
            parent = self
        b = tk.Button(
            parent,
            text=label,
            font=FONT_BTN,
            fg=BTN_FG,
            bg=ACCENT,
            activebackground=ACCENT_DARK,
            activeforeground=BTN_FG,
            relief="flat",
            cursor="hand2",
            width=22,
            pady=10,
            command=cmd,
        )
        b.bind("<Enter>", lambda e: b.config(bg=ACCENT_DARK))
        b.bind("<Leave>", lambda e: b.config(bg=ACCENT))
        tip = tk.Label(self, text=tooltip, font=("Segoe UI", 8),
                       fg="#5a8a6a", bg=BG)
        b.bind("<Enter>", lambda e, t=tip: (b.config(bg=ACCENT_DARK),
                                            t.pack()), add="+")
        b.bind("<Leave>", lambda e, t=tip: (b.config(bg=ACCENT),
                                            t.pack_forget()), add="+")
        return b

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    # ---------------------------------------------------------------- update banner

    def _on_update_available(self, tag: str):
        """Called on the main thread when a newer release is found."""
        if self._update_frame:
            return  # already shown

        frame = tk.Frame(self, bg=UPDATE_BG, pady=8)
        frame.pack(fill="x", side="bottom")

        tk.Label(
            frame,
            text=f"🔄  Update available: {tag}",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT,
            bg=UPDATE_BG,
        ).pack(side="left", padx=(16, 8))

        self._prog_bar_frame = tk.Frame(frame, bg=UPDATE_BG)

        update_btn = tk.Button(
            frame,
            text="Update Now",
            font=("Segoe UI", 10, "bold"),
            fg=BTN_FG,
            bg=ACCENT,
            activebackground=ACCENT_DARK,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=4,
            command=lambda: self._start_update(update_btn),
        )
        update_btn.pack(side="right", padx=(8, 16))

        self._update_frame = frame

    def _start_update(self, btn: tk.Button):
        btn.config(state="disabled", text="Downloading…")
        self._status("Downloading update…")

        # Show a simple progress bar
        bar_bg = tk.Frame(self._update_frame, bg="#0e3c26",
                          width=200, height=6)
        bar_bg.pack(side="left", padx=8)
        bar_bg.pack_propagate(False)
        self._bar_fill = tk.Frame(bar_bg, bg=ACCENT, width=0, height=6)
        self._bar_fill.place(x=0, y=0, relheight=1, width=0)

        def progress(frac: float):
            self.after(0, lambda f=frac: self._bar_fill.place(
                x=0, y=0, relheight=1, width=int(200 * f)
            ))

        self._updater.download_and_install(progress_cb=progress)

    # ---------------------------------------------------------------- entry helpers

    _PLACEHOLDER = "192.168.1.x:8765"

    def _entry_focus_in(self, _event):
        if self._host_var.get() == self._PLACEHOLDER:
            self._host_var.set("")
            self._host_entry.config(fg=TEXT)

    def _entry_focus_out(self, _event):
        if not self._host_var.get().strip():
            self._host_var.set(self._PLACEHOLDER)
            self._host_entry.config(fg="#5a8a6a")

    # ---------------------------------------------------------------- actions

    def _solo(self):
        self._status("Launching solo game…")
        threading.Thread(target=self._run_and_wait,
                         args=("fuzhou_mahjong.ui.client", "--solo"),
                         daemon=True).start()

    def _host(self):
        self._status("Starting server on port 8765…")

        try:
            self._server_proc = _run_module(
                "fuzhou_mahjong.net.server",
                "--host", "0.0.0.0",
                "--port", "8765",
            )
        except Exception as exc:
            messagebox.showerror("Server error", str(exc))
            self._status("Server failed to start.")
            return

        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "your-ip"
        self._status(f"Server running ✓  Tell friends: {ip}:8765")

        self.after(800, lambda: threading.Thread(
            target=self._run_and_wait,
            args=("fuzhou_mahjong.ui.client", "--host", "ws://127.0.0.1:8765"),
            daemon=True,
        ).start())

    def _join(self):
        addr = self._host_var.get().strip()
        if not addr or addr == self._PLACEHOLDER:
            messagebox.showwarning("No address", "Enter the host's IP:port first.")
            return
        if not addr.startswith("ws://") and not addr.startswith("wss://"):
            addr = f"ws://{addr}"
        self._status(f"Connecting to {addr}…")
        threading.Thread(
            target=self._run_and_wait,
            args=("fuzhou_mahjong.ui.client", "--host", addr),
            daemon=True,
        ).start()

    # ---------------------------------------------------------------- helpers

    def _run_and_wait(self, module: str, *args: str):
        try:
            proc = _run_module(module, *args)
            proc.wait()
            self._status("")
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Error", str(exc)))

    def _status(self, msg: str):
        self.after(0, lambda: self._status_var.set(msg))

    # ---------------------------------------------------------------- cleanup

    def destroy(self):
        if self._server_proc and self._server_proc.poll() is None:
            self._server_proc.terminate()
        super().destroy()


# ------------------------------------------------------------------ main

if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
