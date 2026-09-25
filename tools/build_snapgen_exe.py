"""Build a portable Windows onedir executable without local user data."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

try:
    import PyInstaller.__main__ as pyinstaller
except ImportError as exc:  # pragma: no cover - exercised by the release host
    raise SystemExit(
        "PyInstaller is required to build the Windows release. "
        "Install it with: python -m pip install pyinstaller"
    ) from exc


ROOT = Path(__file__).resolve().parent.parent
VERSION = str(
    json.loads(
        (ROOT / "snapgen_data" / "meta" / "snapgen_version.json").read_text(
            encoding="utf-8"
        )
    )["version"]
)
RELEASE = ROOT / "tools" / "release"
STAGE = RELEASE / "exe_stage"
WORK = RELEASE / "exe_build"
DIST = RELEASE / "exe_dist"
APP_DIR = DIST / "Tidmunz Studio"
OUTPUT = RELEASE / f"Tidmunz-Studio-v{VERSION}-windows.zip"


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _stage_public_runtime() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    _copy_file(ROOT / "snapgen_gui_v2.py", STAGE / "snapgen_gui_v2.py")
    _copy_file(
        ROOT / "__pycache__" / "snapgen_core.cpython-312.pyc",
        STAGE / "__pycache__" / "snapgen_core.cpython-312.pyc",
    )

    modules = STAGE / "snapgen_modules"
    modules.mkdir()
    for source in sorted((ROOT / "snapgen_modules").glob("*.py")):
        _copy_file(source, modules / source.name)
    mobile = ROOT / "snapgen_modules" / "mobile"
    if mobile.is_dir():
        shutil.copytree(mobile, modules / "mobile")

    vendor = STAGE / "vendor"
    for name in ("tkinterdnd2", "tkinterdnd2-0.5.0.dist-info"):
        source = ROOT / "vendor" / name
        if source.is_dir():
            shutil.copytree(source, vendor / name)

    assets = STAGE / "assets"
    for name in ("tidmun_studio_icon_final.ico", "video_forbidden_words.json"):
        source = ROOT / "assets" / name
        if source.is_file():
            _copy_file(source, assets / name)
    fonts = ROOT / "assets" / "fonts"
    if fonts.is_dir():
        shutil.copytree(fonts, assets / "fonts")

    _copy_file(
        ROOT / "snapgen_data" / "meta" / "snapgen_version.json",
        STAGE / "snapgen_data" / "meta" / "snapgen_version.json",
    )
    for name in (
        "build_update_patch.py",
        "build_snapgen_exe.py",
        "publish_update.ps1",
        "publish_update.cmd",
    ):
        source = ROOT / "tools" / name
        if source.is_file():
            _copy_file(source, STAGE / "tools" / name)

    for name in ("INSTALL_OTHER_MACHINE.md",):
        source = ROOT / "docs" / name
        if source.is_file():
            _copy_file(source, STAGE / "docs" / name)


def _build() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    if DIST.exists():
        shutil.rmtree(DIST)
    if OUTPUT.exists():
        OUTPUT.unlink()
    DIST.mkdir(parents=True)

    stage_args = [
        (STAGE / "snapgen_gui_v2.py", "."),
        (STAGE / "__pycache__", "__pycache__"),
        (STAGE / "snapgen_modules", "snapgen_modules"),
        (STAGE / "vendor", "vendor"),
        (STAGE / "assets", "assets"),
        (STAGE / "snapgen_data", "snapgen_data"),
        (STAGE / "tools", "tools"),
        (STAGE / "docs", "docs"),
    ]
    args = [
        str(ROOT / "snapgen_gui_v2.py"),
        "--name",
        "Tidmunz Studio",
        "--onedir",
        "--console",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
        "--specpath",
        str(WORK),
        "--paths",
        str(ROOT),
        "--paths",
        str(ROOT / "snapgen_modules"),
        "--paths",
        str(ROOT / "vendor"),
        "--icon",
        str(ROOT / "assets" / "tidmun_studio_icon_final.ico"),
        "--hidden-import",
        "snapgen_modules.story_consistency",
    ]
    for source, target in stage_args:
        if source.exists():
            args.extend(["--add-data", f"{source};{target}"])
    pyinstaller.run(args)


def _write_archive() -> None:
    if not APP_DIR.is_dir():
        raise RuntimeError(f"PyInstaller output missing: {APP_DIR}")
    readme = APP_DIR / "README_EXE.txt"
    readme.write_text(
        "ติดมันส์ สตูดิโอ - Windows portable release\n\n"
        "แตก ZIP ทั้งโฟลเดอร์ แล้วเปิด Tidmunz Studio.exe\n"
        "Bridge และบัญชี ChatGPT เป็นของแต่ละเครื่อง ต้องตั้งค่าในเครื่องนั้นเอง\n",
        encoding="utf-8",
    )

    entries = []
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(APP_DIR.rglob("*")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            name = (Path(APP_DIR.name) / path.relative_to(APP_DIR)).as_posix()
            entries.append(
                {
                    "path": name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
            )
            archive.writestr(name, data)
        manifest = {
            "version": VERSION,
            "type": "windows-onedir",
            "entrypoint": "Tidmunz Studio/Tidmunz Studio.exe",
            "files": entries,
        }
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
    print(OUTPUT)
    print(f"version={VERSION} files={len(entries)} sha256={hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}")


def main() -> int:
    _stage_public_runtime()
    try:
        _build()
        _write_archive()
    finally:
        if STAGE.exists():
            shutil.rmtree(STAGE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
