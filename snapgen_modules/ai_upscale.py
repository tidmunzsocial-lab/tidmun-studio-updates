# -*- coding: utf-8 -*-
"""AI video upscaling using Real-ESRGAN NCNN Vulkan.

Uses the same Vulkan backend approach as RIFE so it works on NVIDIA, AMD,
and Intel GPUs without CUDA.  Falls back to CPU when no Vulkan GPU is found.
"""
import os, re, shutil, subprocess, sys, tempfile, threading, zipfile
from pathlib import Path

# Real-ESRGAN ncnn-vulkan 20220424-windows release
REALESRGAN_RELEASE_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
)
_tool_install_lock = threading.Lock()


def _video_ok(path):
    """Check if video file exists and is non-empty."""
    try:
        return Path(path).is_file() and Path(path).stat().st_size > 0
    except Exception:
        return False


def _ffmpeg_bin():
    """Return a usable ffmpeg executable path (same logic as ai_slow2x)."""
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        project_root / "snapgen_data" / "tools" / "ffmpeg" / "ffmpeg.exe",
        project_root / "tools" / "ffmpeg" / "ffmpeg.exe",
        project_root / "ffmpeg.exe",
    ]
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(Path(found))
    for c in candidates:
        try:
            if Path(c).is_file():
                return str(c)
        except Exception:
            pass
    return "ffmpeg"


def _realesrgan_install_complete(folder):
    folder = Path(folder)
    required = (
        folder / "realesrgan-ncnn-vulkan.exe",
        folder / "vcomp140.dll",
        folder / "models" / "x2plus.param",
        folder / "models" / "x2plus.bin",
    )
    return all(path.is_file() and path.stat().st_size > 0 for path in required)


def ensure_realesrgan_tool(log=None):
    """Download and atomically install the Real-ESRGAN NCNN Vulkan package."""
    say = log if callable(log) else (lambda _msg: None)
    project_root = Path(__file__).resolve().parent.parent
    candidate_dirs = [
        project_root / "snapgen_data" / "tools" / "realesrgan-ncnn-vulkan",
        Path(__file__).resolve().parent / "realesrgan-ncnn-vulkan",
    ]
    for folder in candidate_dirs:
        if _realesrgan_install_complete(folder):
            return str(folder / "realesrgan-ncnn-vulkan.exe")

    with _tool_install_lock:
        for folder in candidate_dirs:
            if _realesrgan_install_complete(folder):
                return str(folder / "realesrgan-ncnn-vulkan.exe")
        if os.name != "nt":
            raise RuntimeError("Real-ESRGAN ชุดนี้รองรับ Windows เท่านั้น")
        if "ARM" in os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64").upper():
            raise RuntimeError("Real-ESRGAN รุ่น Windows นี้ไม่รองรับเครื่อง ARM64")
        import urllib.request
        rg_dir = candidate_dirs[0]
        tools_dir = rg_dir.parent
        tools_dir.mkdir(parents=True, exist_ok=True)
        say("[upscale] เครื่องนี้ยังไม่มี Real-ESRGAN — กำลังดาวน์โหลดชุด AI ครั้งแรก...")
        with tempfile.TemporaryDirectory(prefix="snapgen-esrgan-install-") as td:
            temp = Path(td)
            archive = temp / "esrgan.zip"
            request = urllib.request.Request(REALESRGAN_RELEASE_URL, headers={"User-Agent": "Tidmun-Studio/1.0"})
            with urllib.request.urlopen(request, timeout=180) as response, archive.open("wb") as out:
                shutil.copyfileobj(response, out)
            if not zipfile.is_zipfile(archive):
                raise RuntimeError("ไฟล์ Real-ESRGAN ที่ดาวน์โหลดมาไม่ใช่ ZIP ที่ถูกต้อง")
            extracted = temp / "extracted"
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(extracted)
            exe = next(extracted.rglob("realesrgan-ncnn-vulkan.exe"), None)
            if exe is None:
                raise RuntimeError("ดาวน์โหลด Real-ESRGAN แล้วแต่ไม่พบ realesrgan-ncnn-vulkan.exe")
            package_root = exe.parent
            if not _realesrgan_install_complete(package_root):
                raise RuntimeError("แพ็กเกจ Real-ESRGAN ดาวน์โหลดไม่ครบ (.exe/DLL/model ขาด)")
            incoming = tools_dir / "realesrgan-ncnn-vulkan.installing"
            shutil.rmtree(incoming, ignore_errors=True)
            shutil.copytree(package_root, incoming)
            shutil.rmtree(rg_dir, ignore_errors=True)
            os.replace(str(incoming), str(rg_dir))
        if not _realesrgan_install_complete(rg_dir):
            raise RuntimeError("ติดตั้ง Real-ESRGAN ไม่สมบูรณ์")
        say("[upscale] ติดตั้ง Real-ESRGAN ครบแล้ว")
        return str(rg_dir / "realesrgan-ncnn-vulkan.exe")


def _probe_video(ffmpeg, path):
    """Read resolution and FPS from FFmpeg without ffprobe."""
    r = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    text = (r.stderr or "") + "\n" + (r.stdout or "")
    video_line = next((line for line in text.splitlines() if "Video:" in line), "")
    size_match = re.search(r"(?:^|[^0-9])(\d{2,5})x(\d{2,5})(?:[^0-9]|$)", video_line)
    width, height = (int(size_match.group(1)), int(size_match.group(2))) if size_match else (0, 0)
    fps_match = re.search(r"(?:,|\s)(\d+(?:\.\d+)?)\s+fps(?:,|\s)", video_line)
    fps = float(fps_match.group(1)) if fps_match else 24.0
    if fps <= 0 or fps > 240:
        fps = 24.0
    has_audio = any("Audio:" in line for line in text.splitlines())
    return width, height, fps, has_audio


def upscale_video_ai(input_video, output_video=None, target_height=720, log=None, **_kwargs):
    """Upscale a video to approximately *target_height* using Real-ESRGAN.

    Strategy:
      1. Extract every frame as PNG.
      2. Run Real-ESRGAN x2plus (2x upscale) on each frame.
      3. Re-encode with FFmpeg, resizing to exactly target_height if the
         2x result overshoots.

    Real-ESRGAN ncnn-vulkan auto-detects the best available GPU (Vulkan).
    On machines without a Vulkan GPU it falls back to CPU automatically.
    """
    def say(msg):
        if callable(log):
            try:
                log(msg)
            except Exception:
                pass

    inp = Path(input_video)
    if not _video_ok(inp):
        say(f"[upscale] หาไฟล์วิดีโอไม่เจอ — ข้าม AI upscale: {input_video}")
        return str(input_video)

    if output_video is None:
        output_video = str(inp.with_name(inp.stem + f"_ai{target_height}p" + inp.suffix))
    out = Path(output_video)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        esrgan = ensure_realesrgan_tool(log=say)
        ffmpeg = _ffmpeg_bin()
        width, height, fps, has_audio = _probe_video(ffmpeg, inp)
        if width == 0 or height == 0:
            raise RuntimeError("อ่านความละเอียดวิดีโอไม่ได้")

        say(f"[upscale] Real-ESRGAN AI | ต้นฉบับ {width}x{height} → {target_height}p")

        tmp_dir = Path(tempfile.mkdtemp(prefix="snapgen_esgran_"))
        try:
            in_dir = tmp_dir / "in"
            out_dir = tmp_dir / "out"
            in_dir.mkdir()
            out_dir.mkdir()

            # Extract frames
            say("[upscale] กำลังแตกเฟรม...")
            extracted = subprocess.run(
                [ffmpeg, "-y", "-i", str(inp), "-vsync", "0", str(in_dir / "%08d.png")],
                capture_output=True, text=True, timeout=900,
            )
            if extracted.returncode:
                raise RuntimeError((extracted.stderr or extracted.stdout or "extract frames failed")[-1200:])
            input_count = len(list(in_dir.glob("*.png")))
            if input_count < 1:
                raise RuntimeError("พบเฟรมต้นฉบับ 0 เฟรม")

            # Run Real-ESRGAN x2
            say(f"[upscale] Real-ESRGAN กำลังขยาย {input_count} เฟรม (2x)...")
            esrgan_cmd = [
                esrgan, "-i", str(in_dir), "-o", str(out_dir),
                "-n", "x2plus", "-s", "2", "-f", "%08d.png",
            ]
            r = subprocess.run(
                esrgan_cmd, cwd=str(Path(esrgan).parent),
                capture_output=True, text=True, timeout=7200,
            )
            if r.returncode:
                # Retry with CPU mode (-g -1) like RIFE fallback
                say("[upscale] Real-ESRGAN GPU ใช้ไม่ได้ — ลอง CPU (ช้ากว่า)")
                shutil.rmtree(out_dir, ignore_errors=True)
                out_dir.mkdir()
                r = subprocess.run(
                    [*esrgan_cmd, "-g", "-1"],
                    cwd=str(Path(esrgan).parent),
                    capture_output=True, text=True, timeout=14400,
                )
                if r.returncode:
                    raise RuntimeError((r.stderr or r.stdout or "Real-ESRGAN GPU และ CPU ใช้ไม่ได้")[-1200:])

            output_count = len(list(out_dir.glob("*.png")))
            if output_count < 1:
                raise RuntimeError("Real-ESRGAN คืนเฟรม 0")
            say(f"[upscale] ได้ {output_count} เฟรม กำลังเข้ารหัสวิดีโอ...")

            # Re-encode.  If the 2x result is larger than target, resize down
            # with lanczos so the final output is exactly target_height.
            after_2x_h = height * 2
            vf = []
            if after_2x_h > target_height + 2:
                vf = ["-vf", f"scale=-2:{target_height}:flags=lanczos"]

            fps_text = f"{fps:.6f}".rstrip("0").rstrip(".")
            encode = [
                ffmpeg, "-y", "-framerate", fps_text, "-i", str(out_dir / "%08d.png"),
            ]
            if vf:
                encode += vf
            if has_audio:
                encode += [
                    "-i", str(inp),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:a", "aac", "-b:a", "192k",
                ]
            else:
                encode += ["-map", "0:v:0", "-an"]
            encode += [
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
            ]
            r = subprocess.run(encode, capture_output=True, text=True, timeout=1800)
            if r.returncode:
                raise RuntimeError((r.stderr or r.stdout or "ffmpeg encode failed")[-1200:])
            if _video_ok(out):
                say(f"[upscale] Real-ESRGAN เสร็จ: {out.name}")
                return str(out)
            raise RuntimeError("ไฟล์เอาต์พุตไม่ถูกต้อง")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as e:
        say(f"[upscale] Real-ESRGAN ทำงานไม่สำเร็จ — ใช้วิดีโอต้นฉบับ: {e}")
        return str(inp)
