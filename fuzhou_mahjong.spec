# fuzhou_mahjong.spec  —  PyInstaller build specification
#
# Build command (run from the repo root on Windows):
#   pyinstaller fuzhou_mahjong.spec
#
# Output:  dist\FuzhouMahjong\FuzhouMahjong.exe  (+ supporting files)
# Zip up the entire  dist\FuzhouMahjong\  folder and share it with friends.

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import os

block_cipher = None

# ── source files ─────────────────────────────────────────────────────────────

a = Analysis(
    ["launcher.py"],                        # entry point
    pathex=["."],                           # repo root
    binaries=collect_dynamic_libs("pygame"),  # SDL2 .dlls etc.
    datas=[
        # Version file — imported by launcher.py at runtime
        ("version.py", "."),
        # Bundle all tile PNGs so the game can find them at runtime
        (
            os.path.join("fuzhou_mahjong", "assets", "tiles", "*.png"),
            os.path.join("assets", "tiles"),
        ),
        # Include the full fuzhou_mahjong package as data (needed for -m module
        # spawning from the launcher via subprocess)
        *collect_data_files("fuzhou_mahjong"),
    ],
    hiddenimports=[
        # pygame sub-modules that PyInstaller may miss
        "pygame",
        "pygame.font",
        "pygame.mixer",
        "pygame.image",
        "pygame.transform",
        "pygame.draw",
        # websockets
        "websockets",
        "websockets.legacy",
        "websockets.legacy.server",
        "websockets.legacy.client",
        # game package modules
        "fuzhou_mahjong",
        "fuzhou_mahjong.game",
        "fuzhou_mahjong.game.ai",
        "fuzhou_mahjong.game.deck",
        "fuzhou_mahjong.game.hand",
        "fuzhou_mahjong.game.melds",
        "fuzhou_mahjong.game.score",
        "fuzhou_mahjong.game.state",
        "fuzhou_mahjong.game.tiles",
        "fuzhou_mahjong.game.win",
        "fuzhou_mahjong.ui",
        "fuzhou_mahjong.ui.client",
        "fuzhou_mahjong.ui.render_tiles",
        "fuzhou_mahjong.net",
        "fuzhou_mahjong.net.server",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Strip things we don't need to keep the build smaller
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "tkinter.test",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── package ───────────────────────────────────────────────────────────────────

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── executable ────────────────────────────────────────────────────────────────

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FuzhouMahjong",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                       # compress if UPX is installed (optional)
    console=False,                  # no black terminal window on launch
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="fuzhou_mahjong/assets/icon.ico",  # uncomment if you add an icon
)

# ── collect into one folder ───────────────────────────────────────────────────

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FuzhouMahjong",           # → dist/FuzhouMahjong/
)
