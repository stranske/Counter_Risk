# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Counter Risk CLI release executable."""

from __future__ import annotations

from pathlib import Path


try:
    project_root = Path(__file__).resolve().parent
except NameError:
    project_root = Path.cwd().resolve()

datas = []
for relative_path in ("templates", "config"):
    source_path = project_root / relative_path
    if source_path.exists():
        datas.append((str(source_path), relative_path))

fixture_template = project_root / "tests" / "fixtures" / "Monthly Counterparty Exposure Report.pptx"
if fixture_template.exists():
    datas.append((str(fixture_template), "templates"))


a = Analysis(
    [str(project_root / "src" / "counter_risk" / "cli" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["counter_risk.gui.runner", "tkinter", "tkinter.ttk"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "pyinstaller_runtime_hook.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="counter-risk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX disabled: UPX-packed exes trigger false-positive SmartScreen/AV alerts
    # on Windows operator machines, especially when the exe is unsigned.
    # After building, sign with Authenticode via:
    #   signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 \
    #       /f <cert.pfx> /p <password> dist\counter-risk\counter-risk.exe
    # Without a code-signing cert, instruct operators: Windows protected your PC
    # → click "More info" → "Run anyway".
    upx=False,
    contents_directory=".",
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="counter-risk",
)
