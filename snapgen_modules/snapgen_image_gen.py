# -*- coding: utf-8 -*-
"""snapgen_image_gen.py — standalone image generation via chatgpt-api bridge.

All pages (Image AI, Ref, Prop, Story Face) call generate_image() here.
Single source of truth — fix once, all pages benefit.
No dependency on pyc internals. Uses urllib.request directly (no curl subprocess).
"""

import os, json, time, threading, urllib.request, urllib.error, base64, shutil
import re
from datetime import datetime, timezone
from pathlib import Path

# ── Config (override via set_config) ──────────────────────────────
BRIDGE_URL = "http://127.0.0.1:8000"
BRIDGE_KEY = "local-dev-key"
MODEL = "gpt-5-5"
DEFAULT_OUTPUT_DIR = None  # set at runtime
TIMEOUT = 300  # seconds per request
RETRY_COUNT = 0
RETRY_DELAY = 5  # seconds between retries

# ── State ─────────────────────────────────────────────────────────
_queue_lock = threading.Lock()
_active_count = 0
_active_lock = threading.Lock()
_log_fn = None  # callable(msg: str)


def set_config(*, bridge_url=None, bridge_key=None, model=None,
               output_dir=None, timeout=None, retry_count=None,
               retry_delay=None, log_fn=None):
    """Override defaults. Call once at startup."""
    global BRIDGE_URL, BRIDGE_KEY, MODEL, DEFAULT_OUTPUT_DIR
    global TIMEOUT, RETRY_COUNT, RETRY_DELAY, _log_fn
    if bridge_url is not None:
        BRIDGE_URL = bridge_url.rstrip("/")
    if bridge_key is not None:
        BRIDGE_KEY = bridge_key
    if model is not None:
        MODEL = model
    if output_dir is not None:
        DEFAULT_OUTPUT_DIR = output_dir
    if timeout is not None:
        TIMEOUT = timeout
    if retry_count is not None:
        RETRY_COUNT = retry_count
    if retry_delay is not None:
        RETRY_DELAY = retry_delay
    if log_fn is not None:
        _log_fn = log_fn


def _log(msg):
    if _log_fn:
        try:
            _log_fn(msg)
        except Exception:
            pass


def _slug(text, max_len=40):
    """Safe filename slug from prompt text."""
    import re
    s = text.strip().lower()
    s = re.sub(r'[^a-z0-9\u0E00-\u0E7F\s_-]', '', s)
    s = re.sub(r'\s+', '-', s)
    return s[:max_len].strip("-") or "image"


def _scene_slug(text, max_len=64):
    """Readable scene filename while preserving the source Prompt number."""
    import re
    raw = str(text or "").strip()
    # Keep slot/order prefix if caller sends it, but use the scene sentence for the rest.
    prefix = ""
    m = re.match(r"^\s*(\d{1,2})[_\-\s]+(.+)$", raw, flags=re.S)
    if m:
        prefix = f"{int(m.group(1)):02d}_"
        raw = m.group(2).strip()

    # Prompt scaffolding is intentionally repeated for continuity, but it is
    # not a useful filename.  Keep the Prompt number above for old-file
    # compatibility, then name the image from its actual visible subject.
    raw = re.sub(
        r"^\s*(?:สร้างรูปภาพ(?:จริงหนึ่งรูป)?|สร้างภาพ|วาดภาพ|create(?:\s+an?)?\s+image|generate(?:\s+an?)?\s+image)\s*[:：-]?\s*",
        "",
        raw,
        flags=re.I,
    )
    raw = re.sub(
        r"^\s*(?:(?:keyframe|เฟรมเริ่มต้น|ภาพเริ่มต้น|starting\s+frame|start\s+frame)\s*)+[:：-]?\s*",
        "",
        raw,
        flags=re.I,
    )
    raw = re.sub(
        r"^\s*(?:(?:extreme\s+)?(?:close[- ]?up|medium(?:\s+wide|\s+close[- ]?up)?|wide|long|full)\s+shot\s*)?"
        r"(?:เลนส์\s*\d+\s*mm\s*)?"
        r"(?:มุม(?:ระดับสายตา|สูง(?:เล็กน้อย)?|ต่ำ(?:เล็กน้อย)?|ด้านข้าง|ตรง|เฉียง)\s*)?",
        "",
        raw,
        flags=re.I,
    )
    cut_markers = (
        "ภาพนิ่ง", "cinematic", "wide shot", "medium shot", "close-up",
        "เลนส์", "lens", "foreground", "midground", "background",
        "shot", "perspective", "camera", "lighting", "โทนภาพ",
    )
    lowered = raw.lower()
    cut_at = min((lowered.find(x) for x in cut_markers if lowered.find(x) > 0), default=-1)
    if cut_at > 0:
        raw = raw[:cut_at]
    raw = re.split(r"[.!?\n\r]", raw, 1)[0]
    raw = re.sub(r"[^a-zA-Z0-9\u0E00-\u0E7F\s_-]+", " ", raw)
    words = re.findall(r"[^\s_-]+", raw)
    if words:
        raw = "_".join(words[:5])
    else:
        raw = re.sub(r"\s+", "_", raw).strip("_")
    return (prefix + raw[:max_len].strip("_")) or "image"


def _unique_output_path(out_dir, stem, suffix):
    """Avoid overwriting without putting a date/time in the visible filename."""
    dest = Path(out_dir) / f"{stem}{suffix}"
    if not dest.exists():
        return dest
    number = 2
    while True:
        candidate = Path(out_dir) / f"{stem}_{number}{suffix}"
        if not candidate.exists():
            return candidate
        number += 1


def _download(url, dest, timeout=120):
    """Download file from URL to local path."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
    return dest


def _artifact_snapshot():
    """Return current Bridge artifact IDs; failure is harmless."""
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}/v1/chatgpt/admin/artifacts?limit=10",
            headers={"Authorization": f"Bearer {BRIDGE_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        rows = data.get("artifacts") if isinstance(data, dict) else []
        return {str(x.get("file_id") or "") for x in rows or [] if isinstance(x, dict)}
    except Exception:
        return set()


def _recover_new_artifact(before_ids, started_at, out_dir, name_hint, prompt, log):
    """Recover an image saved by Bridge when the HTTP response was lost.

    The Bridge has a global one-image queue, and we also exclude every artifact
    that existed before this request, so this cannot pick an older user's file.
    """
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}/v1/chatgpt/admin/artifacts?limit=10",
            headers={"Authorization": f"Bearer {BRIDGE_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        rows = data.get("artifacts") if isinstance(data, dict) else []
        candidates = []
        for item in rows or []:
            if not isinstance(item, dict) or item.get("kind") != "image":
                continue
            file_id = str(item.get("file_id") or "")
            if not file_id or file_id in before_ids:
                continue
            created = str(item.get("created_at") or "").replace("Z", "+00:00")
            try:
                created_ts = datetime.fromisoformat(created).astimezone(timezone.utc).timestamp()
            except Exception:
                created_ts = 0
            if created_ts + 10 < started_at:
                continue
            candidates.append((created_ts, item))
        if not candidates:
            return None
        item = max(candidates, key=lambda row: row[0])[1]
        slug = _scene_slug(str(name_hint or prompt), max_len=64)
        dest = _unique_output_path(Path(out_dir), slug, ".png")
        src_path = Path(str(item.get("path") or ""))
        if src_path.is_file():
            shutil.copyfile(str(src_path), str(dest))
        else:
            url = str(item.get("download_url") or "")
            if not url:
                return None
            if url.startswith("/"):
                url = f"{BRIDGE_URL}{url}"
            download_req = urllib.request.Request(url, headers={"Authorization": f"Bearer {BRIDGE_KEY}"})
            with urllib.request.urlopen(download_req, timeout=60) as response, open(dest, "wb") as output:
                shutil.copyfileobj(response, output)
        if dest.is_file() and dest.stat().st_size > 0:
            log(f"[image-gen] ✓ กู้รูปที่ Bridge สร้างเสร็จแล้วกลับมาอัตโนมัติ: {dest}")
            return str(dest)
    except Exception:
        pass
    return None


def generate_image(prompt, *, output_dir=None, name_hint=None,
                   is_edit=False, ref_images=None, aspect_ratio="1:1",
                   save_sidecar=True, log_fn=None):
    """Generate one image via chatgpt-api bridge.

    Returns local path to downloaded image, or raises RuntimeError.

    Args:
        prompt: image generation prompt
        output_dir: where to save (default: DEFAULT_OUTPUT_DIR or cwd/ai_images)
        name_hint: filename prefix (default: slug of prompt)
        is_edit: use /images/edits endpoint (requires ref_images)
        ref_images: list of base64-encoded reference images for edit mode
        aspect_ratio: "1:1", "16:9", "9:16", etc.
        save_sidecar: save .txt sidecar with prompt
        log_fn: per-call log function (falls back to global _log_fn)
    """
    log = log_fn or _log

    # ── Build payload ──────────────────────────────────────────
    # A detailed cinematic prompt by itself can make ChatGPT answer with text
    # instead of reliably invoking its image tool.  The browser succeeds when
    # the user explicitly asks it to create an image, so enforce that same
    # intent centrally for every SnapGen page without changing visual details.
    submitted_prompt = str(prompt or "").strip()
    if not re.match(r"^(?:สร้าง|วาด|generate|create|make)\s*(?:รูป|ภาพ|image|an?\s+image)", submitted_prompt, re.I):
        action = "แก้ไขและสร้างรูปภาพใหม่จริงหนึ่งรูป" if is_edit else "สร้างรูปภาพจริงหนึ่งรูป"
        submitted_prompt = (
            f"{action}ตามคำอธิบายต่อไปนี้ ใช้เครื่องมือสร้างภาพทันที "
            "ห้ามตอบเป็นข้อความ ห้ามอธิบาย และต้องส่งผลลัพธ์เป็นรูปภาพ:\n\n"
            + submitted_prompt
        )
    endpoint = "/v1/images/edits" if is_edit else "/v1/images/generations"
    payload = {
        "model": MODEL,
        "prompt": submitted_prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json",
    }
    if is_edit and ref_images:
        payload["images"] = ref_images
    if aspect_ratio and aspect_ratio != "1:1":
        payload["aspect_ratio"] = aspect_ratio

    # ── Output dir ─────────────────────────────────────────────
    out_dir = Path(output_dir or DEFAULT_OUTPUT_DIR or os.path.join(os.getcwd(), "ai_images"))
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        project_root = Path(__file__).resolve().parent.parent
        export_root = (project_root / "export").resolve()
        out_resolved = out_dir.resolve()
        if out_resolved == export_root or export_root in out_resolved.parents:
            save_sidecar = False
    except Exception:
        pass

    # ── Retry loop ─────────────────────────────────────────────
    last_error = None
    request_started = time.time()
    artifact_ids_before = set()
    for attempt in range(1 + RETRY_COUNT):
        if attempt > 0:
            log(f"[image-gen] retry {attempt}/{RETRY_COUNT} in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

        try:
            # Hold the lock for the complete HTTP operation.  Previously it
            # protected only Request construction, so another page could send
            # an image job while this request was still running.
            with _queue_lock:
                request_started = time.time()
                artifact_ids_before = _artifact_snapshot()
                data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    f"{BRIDGE_URL}{endpoint}",
                    data=data_bytes,
                    headers={
                        "Authorization": f"Bearer {BRIDGE_KEY}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    result = json.loads(resp.read().decode("utf-8", errors="replace"))

            # ── Parse response ─────────────────────────────────
            if "error" in result:
                err = result["error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                raise RuntimeError(f"Bridge error: {msg}")

            data_list = result.get("data", [])
            if not data_list:
                raise RuntimeError("Bridge returned no data (empty response)")

            slug = _scene_slug(str(name_hint or prompt), max_len=64)
            ext = ".png"
            dest = _unique_output_path(out_dir, slug, ext)

            item = data_list[0]
            b64 = item.get("b64_json")
            src_path = item.get("path")
            if b64:
                dest.write_bytes(base64.b64decode(b64))
            elif src_path and Path(str(src_path)).exists():
                shutil.copyfile(str(src_path), str(dest))
            else:
                url = item.get("url") or item.get("download_url")
                if not url:
                    raise RuntimeError(f"Bridge returned no image bytes/path/url: {json.dumps(item, ensure_ascii=False)[:200]}")
                if url.startswith("/"):
                    url = f"{BRIDGE_URL}{url}"
                _download(url, str(dest), timeout=120)

            # ── Save sidecar ───────────────────────────────────
            if save_sidecar:
                sidecar = out_dir / f"{ts}-{slug}.txt"
                sidecar.write_text(prompt, encoding="utf-8")

            log(f"[image-gen] ✓ {dest}")
            return str(dest)

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            last_error = RuntimeError(f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            last_error = RuntimeError(f"Connection error: {e.reason}")
        except RuntimeError as e:
            last_error = e
        except Exception as e:
            last_error = RuntimeError(f"Unexpected: {e}")

        recovered = _recover_new_artifact(
            artifact_ids_before, request_started, out_dir, name_hint, prompt, log,
        )
        if recovered:
            return recovered

    raise last_error or RuntimeError("Image generation failed after all retries")


def generate_images_batch(prompts, *, output_dir=None, name_hints=None,
                          parallel=False, log_fn=None, **kwargs):
    """Generate multiple images (sequential or parallel).

    Args:
        prompts: list of prompt strings
        name_hints: optional list of filename hints
        parallel: if True, run in threads (max 2 concurrent for bridge)
        **kwargs: passed to generate_image()

    Returns list of (prompt, path_or_error) tuples.
    """
    results = []

    if parallel:
        sem = threading.Semaphore(2)  # bridge concurrency limit
        threads = []

        def _worker(idx, p):
            sem.acquire()
            try:
                hint = name_hints[idx] if name_hints and idx < len(name_hints) else None
                path = generate_image(p, output_dir=output_dir, name_hint=hint,
                                      log_fn=log_fn, **kwargs)
                results.append((p, path))
            except Exception as e:
                results.append((p, e))
            finally:
                sem.release()

        for i, p in enumerate(prompts):
            t = threading.Thread(target=_worker, args=(i, p), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
    else:
        for i, p in enumerate(prompts):
            try:
                hint = name_hints[i] if name_hints and i < len(name_hints) else None
                path = generate_image(p, output_dir=output_dir, name_hint=hint,
                                      log_fn=log_fn, **kwargs)
                results.append((p, path))
            except Exception as e:
                results.append((p, e))

    return results


# ── Convenience: encode image to base64 for edit mode ────────────
def encode_image_b64(path):
    """Read image file and return base64 string."""
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")
