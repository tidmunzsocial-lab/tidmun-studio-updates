# -*- coding: utf-8 -*-
"""SnapGen prop page.

This module owns the widgets, state, and callbacks for this page only.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
import os
import shutil
import subprocess
import threading
import time
from snapgen_page_builder import (
    make_log_box as _builder_make_log_box,
    append_log as _builder_append_log,
    make_selection_lock_bar as _builder_make_selection_lock_bar,
    set_selection_lock as _builder_set_selection_lock,
    set_selection_locks as _builder_set_selection_locks,
    remove_selection_lock as _builder_remove_selection_lock,
)


def install(g: dict, root: tk.Misc) -> tk.Misc:
    """Build this page and return its root frame."""
    globals().update(g)
    lock_g = {"_selection_locks": {}, "_selection_lock_vars": []}
    export_prop_dir = g.get("EXPORT_PROP", BASE / "prop")
    prop_page = tk.Frame(root, bg="#FAFAF7")
    g["prop_page"] = prop_page
    prop_name_var = tk.StringVar(value="")
    g["prop_name_var"] = prop_name_var
    prop_job_running = [False]
    prop_make_btn = [None]
    auto_prop_btn = [None]
    auto_prop_running = [False]
    auto_prop_stop = [False]
    prop_ref_image = [None]
    prop_ref_preview_photo = [None]
    prop_ref_paste_busy = [False]
    prop_ref_last_paste = {"sig": None, "time": 0.0}

    def _notify_done():
        notify = g.get("_snapgen_notify_done")
        if callable(notify):
            try:
                notify()
            except Exception:
                pass
    
    prop_box = tk.LabelFrame(prop_page, text="📦 Prop", bg="#FAFAF7", fg="#1A1A1A", padx=10, pady=8)
    prop_box.pack(fill="x", padx=10, pady=10)
    prop_row = tk.Frame(prop_box, bg="#FAFAF7")
    prop_row.pack(fill="x")
    tk.Label(prop_row, text="ชื่อ:", bg="#FAFAF7", fg="#333").pack(side="left")
    prop_entry_wrap = tk.Frame(prop_row, bg="#FFFFFF", highlightthickness=1, highlightbackground="#D1D5DB")
    prop_entry_wrap.pack(side="left", fill="x", expand=True, padx=6)
    prop_entry = tk.Entry(prop_entry_wrap, textvariable=prop_name_var, relief="flat", bg="#FFFFFF", fg="#111")
    prop_entry.pack(fill="x", padx=8, pady=6)
    prop_placeholder = tk.Label(prop_entry_wrap, text="ใส่ชื่อ", bg="#FFFFFF", fg="#B0B0B0", font=("Leelawadee UI", 9))
    prop_placeholder.place(x=10, y=6)
    
    # Category dropdown (5 types — affects cat_hint injected into prompt)
    prop_category_var = tk.StringVar(value="อัตโนมัติ")
    g["prop_category_var"] = prop_category_var
    _PROP_CATEGORIES = ("อัตโนมัติ", "เสื้อผ้า", "อาหาร", "ทั่วไป", "สัตว์")
    _PROP_CAT_HINTS = {
        "อัตโนมัติ": "",
        "เสื้อผ้า": "Clothing / garment prop. Show fabric texture, stitching detail, fold and drape. ",
        "อาหาร": "Food prop. Show fresh texture, natural color, appetizing presentation. ",
        "ทั่วไป": "General everyday object prop. Show material detail, surface texture. ",
        "สัตว์": "Animal prop. Show natural fur/skin/feather texture, lifelike pose. ",
    }
    g["_PROP_CAT_HINTS"] = _PROP_CAT_HINTS
    tk.Label(prop_row, text="หมวด:", bg="#FAFAF7", fg="#333").pack(side="left", padx=(8, 0))
    prop_cat_menu = tk.OptionMenu(prop_row, prop_category_var, *_PROP_CATEGORIES)
    prop_cat_menu.config(relief="flat", bg="#FFFFFF", fg="#111", font=("Leelawadee UI", 9), highlightthickness=1, highlightbackground="#D1D5DB")
    prop_cat_menu.pack(side="left", padx=4)
    g["prop_cat_menu"] = prop_cat_menu
    g["_prop_selected_context"] = {}
    def _sync_prop_placeholder(*_):
        try:
            if prop_name_var.get().strip(): prop_placeholder.place_forget()
            else: prop_placeholder.place(x=10, y=6)
        except Exception:
            pass
    prop_name_var.trace_add("write", _sync_prop_placeholder)
    prop_entry.bind("<FocusIn>", lambda _e: _sync_prop_placeholder(), add="+")
    
    # Prop Select — opens character/prop list from prompt_ref_context.json
    def _prop_item_name(item):
        if isinstance(item, dict):
            for key in ("name", "ชื่อ", "item", "prop", "object"):
                val = str(item.get(key, "")).strip()
                if val:
                    return val
            return ""
        return str(item).strip()

    def _prop_item_detail(item):
        if isinstance(item, dict):
            parts = []
            for key in ("description", "รายละเอียด", "note", "ลักษณะ", "material", "วัสดุ", "color", "สี", "usage", "การใช้งาน"):
                val = str(item.get(key, "")).strip()
                if val and val.lower() != "ไม่ระบุ":
                    parts.append(f"{key}: {val}")
            return "; ".join(parts)
        return str(item).strip()

    def _extract_context_props(text):
        try:
            import json as _json
            ctx = _json.loads(text)
            props = ctx.get("props", []) if isinstance(ctx, dict) else []
        except Exception:
            props = []
        out = []
        seen = set()
        for item in props:
            name = _prop_item_name(item)
            if not name or name.lower() == "ไม่ระบุ" or name in seen:
                continue
            seen.add(name)
            out.append((name, item))
        return out

    def _apply_prop_character(item, selector=None):
        # item comes from props[] only
        if isinstance(item, dict):
            name = _prop_item_name(item)
        else:
            name = str(item).strip()
        prop_name_var.set(name)
        if name:
            g["_prop_selected_context"][name] = _prop_item_detail(item)
        _prop_log(_builder_set_selection_lock(lock_g, "prop", name))
        if selector is not None:
            selector.destroy()
    
    def _open_prop_selector():
        # Pull from `props` array in prompt_ref_context.json
        try:
            import json as _json
            context_text = _load_ref_context()
            ctx = _json.loads(context_text)
        except Exception:
            ctx = {}
        items = _extract_context_props(context_text)
        if not items:
            _prop_log("[Select] ไม่พบรายการ prop ใน prompt_ref_context.json (props[] ว่าง)")
            return
        selector = tk.Toplevel(root)
        selector.title("เลือก Prop — จาก Context")
        selector.configure(bg="#FAFAF7")
        selector.resizable(False, False)
        selector.transient(root)
        tk.Label(selector, text=f"เลือก Prop ({len(items)} รายการ)", bg="#FAFAF7", fg="#111", font=("Leelawadee UI", 11, "bold")).pack(fill="x", padx=14, pady=(12, 6))
        for name, item in items:
            detail = _prop_item_detail(item)
            label = name + (f"  —  {detail[:80]}" if detail and detail != name else "")
            tk.Button(selector, text=label, anchor="w", command=lambda c=item: _apply_prop_character(c, selector), bg="#FFFFFF", fg="#111", activebackground="#E0E7FF", activeforeground="#111", relief="flat", bd=0, padx=12, pady=8).pack(fill="x", padx=12, pady=3)
        selector.grab_set()
    
    prop_select_btn = tk.Button(prop_row, text="Select", command=_open_prop_selector, bg="#2563EB", fg="white", activebackground="#1D4ED8", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold"))
    g["prop_select_btn"] = prop_select_btn

    # ── Optional visual reference attachment ───────────────────────────────
    # ใช้เวลาต้องการให้ Prop/3D อิงจากรูปตัวอย่าง เช่น แคปจอแล้ววางเลย
    prop_ref_box = tk.LabelFrame(prop_box, text="รูปแนบตัวอย่าง", bg="#FAFAF7", fg="#1A1A1A", padx=8, pady=6)
    prop_ref_box.pack(fill="x", pady=(8, 0))
    prop_ref_row = tk.Frame(prop_ref_box, bg="#FAFAF7")
    prop_ref_row.pack(fill="x")
    prop_ref_thumb = tk.Label(
        prop_ref_row,
        text="วางรูป / เลือกไฟล์",
        bg="#FFFFFF",
        fg="#6B7280",
        width=18,
        height=6,
        relief="solid",
        bd=1,
        anchor="center",
    )
    prop_ref_thumb.pack(side="left", padx=(0, 8), pady=2)
    prop_ref_info = tk.StringVar(value="ยังไม่มีรูปแนบ")
    prop_ref_controls = tk.Frame(prop_ref_row, bg="#FAFAF7")
    prop_ref_controls.pack(side="left", fill="x", expand=True)
    tk.Label(prop_ref_controls, textvariable=prop_ref_info, bg="#FAFAF7", fg="#374151", anchor="w").pack(fill="x", pady=(0, 5))

    def _set_prop_ref_image(path):
        p = Path(str(path or "")).expanduser()
        if not p.exists() or not p.is_file():
            _prop_log(f"[แนบรูป] ไม่พบไฟล์: {p}")
            return
        old_name = Path(prop_ref_image[0]).name if prop_ref_image[0] else ""
        if old_name:
            _builder_remove_selection_lock(lock_g, "reference", old_name)
        prop_ref_image[0] = str(p)
        prop_ref_info.set(p.name)
        try:
            from PIL import Image, ImageTk
            im = Image.open(p)
            im.thumbnail((150, 110), Image.LANCZOS)
            photo = ImageTk.PhotoImage(im)
            prop_ref_preview_photo[0] = photo
            prop_ref_thumb.config(image=photo, text="", width=150, height=110)
        except Exception:
            prop_ref_thumb.config(image="", text=p.name[:28], width=18, height=6)
        _prop_log(_builder_set_selection_lock(lock_g, "reference", p.name, append=True))

    def _paste_prop_ref_image():
        if prop_ref_paste_busy[0]:
            return
        prop_ref_paste_busy[0] = True
        try:
            from PIL import ImageGrab, Image
            clip = ImageGrab.grabclipboard()
            if clip is None:
                _prop_log("[แนบรูป] clipboard ไม่มีรูป")
                return
            attach_dir = Path(export_prop_dir) / "_attachments"
            attach_dir.mkdir(parents=True, exist_ok=True)
            now = time.time()
            if isinstance(clip, Image.Image):
                sample = clip.convert("RGB").resize((16, 16))
                sig = ("image", clip.size, clip.mode, sample.tobytes())
                if prop_ref_last_paste["sig"] == sig and now - prop_ref_last_paste["time"] < 1.0:
                    return
                prop_ref_last_paste.update({"sig": sig, "time": now})
                out = attach_dir / f"prop_ref_clip_{time.strftime('%Y%m%d-%H%M%S')}.png"
                clip.convert("RGBA").save(out)
                _set_prop_ref_image(out)
                return
            if isinstance(clip, (list, tuple)):
                for item in clip:
                    src = Path(str(item))
                    if src.exists() and src.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                        sig = ("file", str(src.resolve()), src.stat().st_mtime_ns, src.stat().st_size)
                        if prop_ref_last_paste["sig"] == sig and now - prop_ref_last_paste["time"] < 1.0:
                            return
                        prop_ref_last_paste.update({"sig": sig, "time": now})
                        out = attach_dir / src.name
                        if src.resolve() != out.resolve():
                            shutil.copy2(src, out)
                        _set_prop_ref_image(out)
                        return
            _prop_log("[แนบรูป] clipboard ไม่ใช่รูปที่ใช้ได้")
        except Exception as e:
            _prop_log(f"[แนบรูป] วางรูปไม่สำเร็จ: {e}")
        finally:
            prop_ref_paste_busy[0] = False

    def _choose_prop_ref_image():
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="เลือกรูปแนบตัวอย่าง Prop",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")]
            )
            if path:
                _set_prop_ref_image(path)
        except Exception as e:
            _prop_log(f"[แนบรูป] เลือกไฟล์ไม่สำเร็จ: {e}")

    def _clear_prop_ref_image():
        old_name = Path(prop_ref_image[0]).name if prop_ref_image[0] else ""
        prop_ref_image[0] = None
        prop_ref_preview_photo[0] = None
        prop_ref_info.set("ยังไม่มีรูปแนบ")
        prop_ref_thumb.config(image="", text="วางรูป / เลือกไฟล์", width=18, height=6)
        _builder_remove_selection_lock(lock_g, "reference", old_name)
        _prop_log("[แนบรูป] ล้างรูปแนบแล้ว")

    def _run_3d_from_prop_ref():
        if not prop_ref_image[0]:
            _prop_log("[3D] ยังไม่มีรูปแนบ")
            return
        name_hint = prop_name_var.get().strip() or prop_ref_image[0]
        threading.Thread(target=lambda: _run_prop_3d(prop_ref_image[0], name_hint=name_hint), daemon=True).start()

    tk.Button(prop_ref_controls, text="📋 วางรูป", command=_paste_prop_ref_image, bg="#475569", fg="white", relief="flat", padx=12, pady=6, font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=(0, 4))
    tk.Button(prop_ref_controls, text="📎 เลือกไฟล์", command=_choose_prop_ref_image, bg="#475569", fg="white", relief="flat", padx=12, pady=6, font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=4)
    tk.Button(prop_ref_controls, text="🧊 3D จากรูปแนบ", command=_run_3d_from_prop_ref, bg="#0891B2", fg="white", relief="flat", padx=12, pady=6, font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=4)
    tk.Button(prop_ref_controls, text="ล้าง", command=_clear_prop_ref_image, bg="#DC2626", fg="white", relief="flat", padx=12, pady=6, font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=4)
    g["prop_ref_image"] = prop_ref_image

    prop_lock_bar = _builder_make_selection_lock_bar(prop_box, lock_g, bg="#FAFAF7")
    prop_lock_bar.pack(fill="x", pady=(8, 0))
    g["prop_lock_bar"] = prop_lock_bar
    
    prop_log_widget = _builder_make_log_box(prop_box)
    prop_log_widget.pack(fill="x", pady=(8, 0))
    def _prop_log(msg):
        _builder_append_log(prop_log_widget, msg)
    g["_prop_log"] = _prop_log
    
    prop_gallery = tk.LabelFrame(prop_page, text="แกลเลอรี", bg="#FAFAF7", fg="#1A1A1A", padx=8, pady=6)
    prop_gallery.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    prop_gallery_canvas = tk.Canvas(prop_gallery, bg="#FAFAF7", highlightthickness=0)
    prop_gallery_scroll = tk.Scrollbar(prop_gallery, orient="vertical", command=prop_gallery_canvas.yview)
    prop_gallery_canvas.configure(yscrollcommand=prop_gallery_scroll.set)
    prop_gallery_inner = tk.Frame(prop_gallery_canvas, bg="#FAFAF7")
    prop_gallery_inner.bind("<Configure>", lambda e: prop_gallery_canvas.configure(scrollregion=prop_gallery_canvas.bbox("all")))
    _pg_window = prop_gallery_canvas.create_window((0, 0), window=prop_gallery_inner, anchor="nw")
    prop_gallery_canvas.pack(side="left", fill="both", expand=True)
    prop_gallery_scroll.pack(side="right", fill="y")
    g["prop_gallery_inner"] = prop_gallery_inner
    prop_gallery_images = []
    g["prop_gallery_images"] = prop_gallery_images

    def _pg_sync(_e=None):
        prop_gallery_canvas.configure(scrollregion=prop_gallery_canvas.bbox("all") or (0, 0, 0, 0))
        try:
            prop_gallery_canvas.itemconfigure(_pg_window, width=max(prop_gallery_canvas.winfo_width() - 4, 1))
        except Exception:
            pass

    def _pg_on_mousewheel(event):
        try:
            if not prop_gallery_canvas.winfo_exists():
                return
            first, last = prop_gallery_canvas.yview()
            if float(last) - float(first) >= 0.999:
                return
            delta = int(getattr(event, "delta", 0) or 0)
            if delta == 0:
                return
            prop_gallery_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
            return "break"
        except Exception:
            return

    def _pg_bind_wheel(widget):
        try:
            widget.bind("<Enter>", lambda _e: prop_gallery_canvas.bind_all("<MouseWheel>", _pg_on_mousewheel), add="+")
            widget.bind("<Leave>", lambda _e: prop_gallery_canvas.unbind_all("<MouseWheel>"), add="+")
            widget.bind("<MouseWheel>", _pg_on_mousewheel, add="+")
        except Exception:
            pass

    prop_gallery_canvas.bind("<Configure>", _pg_sync)
    for _w in (prop_gallery, prop_gallery_canvas, prop_gallery_inner, prop_gallery_scroll):
        _pg_bind_wheel(_w)
    
    # ── Prop 3D: Hunyuan 3D integration (image → 3D mesh) ──────────────
    prop_3d_dir = export_prop_dir / "3d"
    prop_3d_dir.mkdir(parents=True, exist_ok=True)
    g["prop_3d_dir"] = prop_3d_dir

    def _clean_prop_3d_name(text):
        import re
        name = os.path.splitext(os.path.basename(str(text or "")))[0]
        name = re.sub(r"^\d{8}[-_]\d{6}[-_]*", "", name)
        name = re.sub(r"[_-]slow2x$", "", name, flags=re.I)
        name = re.sub(r"[^0-9A-Za-zก-๙ ]+", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return (name[:40].strip() or "simple object")

    def _build_safe_hunyuan_prop_prompt(name_hint):
        name = _clean_prop_3d_name(name_hint)
        return (
            f"a single {name} object, isolated centered product photo, "
            "plain white background, full object visible, simple realistic material, no text"
        )
    
    def _run_prop_3d(image_path, name_hint=""):
        """Send image to Hunyuan 3D → download GLB + preview into prop_3d/<name>/."""
        try:
            # Import by the full module path so this page can never pick up a
            # stale hunyuan3d.pyc or another same-named module from sys.path.
            from snapgen_modules.hunyuan3d import Hunyuan3DClient, Hunyuan3DError
            # BASE from the recovered app already points at snapgen_data.
            # Resolve from this module instead so the path cannot become
            # snapgen_data/snapgen_data when the runtime environment changes.
            cookie = str(Path(__file__).resolve().parent.parent / "snapgen_data" / "hunyuan_cookies.txt")
            client = Hunyuan3DClient(cookie_file=cookie)
            source = str(image_path or "").strip()
            _prop_log(f"[3D] ส่งรูปไป Hunyuan: {_clean_prop_3d_name(name_hint or source)}")
            # hunyuan3d.py owns the complete local-file/URL flow so every
            # caller behaves the same and this page does not duplicate it.
            task_id = client.image_to_3d(source)
            _prop_log(f"[3D] task_id: {task_id} — รอประมวลผล...")
            result = client.wait_for_task(task_id, timeout=600)
            out_name = _clean_prop_3d_name(name_hint or image_path)
            out_dir = prop_3d_dir / out_name
            out_dir.mkdir(parents=True, exist_ok=True)
            saved = client.download_result(result, out_dir=str(out_dir), formats=["fbx"])
            _prop_log(f"[3D] ✓ สำเร็จ: {saved}")
            # Open output folder
            subprocess.Popen(["explorer", str(out_dir)])
            return saved
        except Exception as e:
            _prop_log(f"[3D] ERROR: {e}")
            return None
    g["_run_prop_3d"] = _run_prop_3d
    
    def _prop_gallery_add(path, prepend=True):
        card = tk.Frame(prop_gallery_inner, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5E7EB")
        thumb_box = tk.Frame(card, bg="#FFFFFF", width=96, height=96)
        thumb_box.pack(side="left", padx=6, pady=6)
        thumb_box.pack_propagate(False)
        try:
            from PIL import Image, ImageTk
            im = Image.open(path)
            im.thumbnail((96, 96), Image.LANCZOS)
            photo = ImageTk.PhotoImage(im)
            prop_gallery_images.append(photo)
            tk.Label(thumb_box, image=photo, bg="#FFFFFF").pack(expand=True)
        except Exception:
            tk.Label(thumb_box, text="ไม่มี preview", bg="#FFFFFF", fg="#9CA3AF", wraplength=80).pack(expand=True)
        tk.Label(card, text=os.path.basename(path), bg="#FFFFFF", fg="#111", anchor="w").pack(side="left", fill="x", expand=True, padx=8, pady=6)
        tk.Button(card, text="📂 เปิด", command=lambda p=path: subprocess.Popen(["explorer", "/select,", p])).pack(side="right", padx=4, pady=4)
        # 🧊 สร้าง 3D button — wire to _run_prop_3d in background thread
        def _do_3d(p=path):
            nm = os.path.splitext(os.path.basename(p))[0]
            def worker():
                _run_prop_3d(p, name_hint=nm)
            threading.Thread(target=worker, daemon=True).start()
        tk.Button(card, text="🧊 สร้าง 3D", command=_do_3d, bg="#0891B2", fg="white", activebackground="#0E7490", activeforeground="white", relief="flat", bd=0, padx=8, pady=4, font=("Leelawadee UI", 8, "bold")).pack(side="right", padx=4, pady=4)
        if prepend:
            card.pack(fill="x", pady=2, side="top")
            card.lift()
            root.after(50, lambda: prop_gallery_canvas.yview_moveto(0.0))
        else:
            card.pack(fill="x", pady=2)
    g["_prop_gallery_add"] = _prop_gallery_add
    
    # Prop prompt builder — single clean object render for 3D, not multi-view sheet
    def _build_prop_prompt(name):
        cat = prop_category_var.get() if "prop_category_var" in g else "อัตโนมัติ"
        cat_hint = _PROP_CAT_HINTS.get(cat, "")
        return (f"Single prop/object render: {name}. {cat_hint}"
                "Show one complete object only, centered, isolated, full object visible, three-quarter front view. "
                "Clean silhouette, clear shape, readable material, realistic scale, no cropping, no duplicate views, no multi-angle sheet. "
                "Plain white or very light gray studio background with soft shadow under the object. "
                "No humans, no characters, no hands, no label strip, no text labels on the object itself. "
                "No environment, no room, no location, no scenes. "
                "Photorealistic product-style studio lighting, sharp focus, high detail, suitable as a source image for 3D generation. No watermark.")
    
    def _set_prop_action_buttons_running(running, auto=False):
        prop_job_running[0] = bool(running)
        try:
            if prop_make_btn[0]:
                prop_make_btn[0].config(state=(tk.DISABLED if running else tk.NORMAL))
            if auto_prop_btn[0] and not auto:
                auto_prop_btn[0].config(state=(tk.DISABLED if running else tk.NORMAL))
        except Exception:
            pass
    
    def _set_auto_prop_button_running(running):
        btn = auto_prop_btn[0]
        if not btn:
            return
        try:
            _set_prop_action_buttons_running(running, auto=True)
            if running:
                btn.config(text="⏹ หยุด", command=stop_auto_prop, state=tk.NORMAL, bg="#DC2626", activebackground="#B91C1C")
            else:
                btn.config(text="⚡ Auto Prop", command=generate_auto_prop, state=tk.NORMAL, bg="#0EA5E9", activebackground="#0284C7")
        except Exception:
            pass
    
    def stop_auto_prop():
        auto_prop_stop[0] = True
        _prop_log("[auto-prop] ขอหยุด — จะหยุดหลังรูปที่กำลังสร้างเสร็จ")
    
    def _run_prop_jobs(names, auto=False):
        names = [n.strip() for n in names if n and n.strip()]
        if not names:
            _prop_log("ไม่มีชื่อสำหรับสร้าง Prop")
            return
        if prop_job_running[0]:
            _prop_log("กำลังสร้างอยู่ — รอให้งานเดิมเสร็จก่อน")
            return
        if auto:
            auto_prop_stop[0] = False
            auto_prop_running[0] = True
            root.after(0, lambda: _set_auto_prop_button_running(True))
        else:
            root.after(0, lambda: _set_prop_action_buttons_running(True, auto=False))
        def worker():
            try:
                lock = globals().get("_bridge_queue_lock")
                def run_one(idx, name):
                    prompt = _build_prop_prompt(name)
                    refine = g.get("_refine_prompt_via_ai") or globals().get("_refine_prompt_via_ai")
                    if callable(refine):
                        _prop_log(f"[refine] ส่ง GPT แปลง prompt Prop: {name}")
                        refined_prompt = refine(prompt, kind="prop")
                        if refined_prompt and refined_prompt != prompt:
                            _prop_log(f"[refine] ได้ prompt ใหม่ ({len(refined_prompt)} chars)")
                            prompt = refined_prompt
                    else:
                        _prop_log("[refine] ไม่เจอตัวแปลง prompt — ใช้ prompt เดิม")
                    if "_wait_bridge_free" in globals():
                        globals()["_wait_bridge_free"](log_fn=_prop_log)
                    if auto and auto_prop_stop[0]:
                        _prop_log(f"[auto-prop] หยุดแล้ว — ข้าม {name}")
                        return
                    _prop_log(f"[auto-prop] {idx}/{len(names)} — เริ่มสร้าง: {name}")
                    payload = {"model":"gpt-5-5", "prompt":prompt, "n":1, "aspect_ratio":"1:1", "history_and_training_disabled":False}
                    ref_path = prop_ref_image[0]
                    if ref_path and os.path.exists(ref_path):
                        enc = g.get("_encode_image_b64") or globals().get("_encode_image_b64")
                        if callable(enc):
                            payload["images"] = [enc(ref_path)]
                            _prop_log(f"[แนบรูป] ส่งไฟล์แนบไปด้วย: {os.path.basename(ref_path)}")
                        else:
                            _prop_log("[แนบรูป] ไม่พบตัวเข้ารหัสรูป — สร้างแบบไม่มีไฟล์แนบ")
                    out = g["_do_image_request"](payload, is_edit=bool(payload.get("images")), prompt=prompt, name_hint=name, raw_prompt=prompt, output_dir=str(export_prop_dir))
                    root.after(0, lambda out=out: (_prop_log(f"✓ {out}"), _prop_gallery_add(out, True), _notify_done()))
                def run_all():
                    for idx, name in enumerate(names, 1):
                        if auto and auto_prop_stop[0]:
                            _prop_log("[auto-prop] หยุดตามคำสั่ง")
                            break
                        run_one(idx, name)
                if lock:
                    with lock: run_all()
                else:
                    run_all()
            except Exception as e:
                root.after(0, lambda e=e: _prop_log(f"ERROR: {e}"))
            finally:
                if auto:
                    auto_prop_running[0] = False
                    root.after(0, lambda: _set_auto_prop_button_running(False))
                else:
                    root.after(0, lambda: _set_prop_action_buttons_running(False, auto=False))
        threading.Thread(target=worker, daemon=True).start()
    
    def generate_prop():
        name = prop_name_var.get().strip()
        if not name:
            _prop_log("ใส่ชื่อก่อน")
            return
        _prop_log(_builder_set_selection_lock(lock_g, "prop", name))
        _run_prop_jobs([name])
    g["generate_prop"] = generate_prop
    
    def generate_auto_prop():
        ctx = _load_ref_context()
        if not ctx.strip():
            _prop_log("ไม่เจอ prompt_ref_context.json")
            return
        items = _extract_context_props(ctx)
        if not items:
            _prop_log("ไม่เจอ props[] ใน Prompt Context")
            return
        for name, item in items:
            g["_prop_selected_context"][name] = _prop_item_detail(item)
        names = [name for name, _item in items]
        _prop_log(_builder_set_selection_locks(lock_g, "prop", names))
        _prop_log("[auto-prop] จะสร้างทีละรูป: " + ", ".join(names))
        _run_prop_jobs(names, auto=True)
    g["generate_auto_prop"] = generate_auto_prop
    
    def clear_prop_gallery():
        for child in prop_gallery_inner.winfo_children():
            child.destroy()
        prop_gallery_images.clear()
        _prop_log("ล้างรูป Prop gallery แล้ว")
    
    make_prop_btn = tk.Button(prop_row, text="📦 สร้าง Prop", command=generate_prop, bg="#6D28D9", fg="white", activebackground="#7C3AED", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold"))
    make_prop_btn.pack(side="left", padx=4)
    prop_make_btn[0] = make_prop_btn
    
    # Pack Select AFTER สร้าง Prop (so สร้าง Prop appears first on the left)
    prop_select_btn.pack(side="left", padx=(0, 4))
    auto_btn_prop = tk.Button(prop_row, text="⚡ Auto Prop", command=generate_auto_prop, bg="#0EA5E9", fg="white", activebackground="#0284C7", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold"))
    auto_btn_prop.pack(side="left", padx=4)
    auto_prop_btn[0] = auto_btn_prop
    tk.Button(prop_row, text="Clear", command=lambda: (prop_name_var.set(""), prop_log_widget.delete("1.0", tk.END)), bg="#DC2626", fg="white", activebackground="#B91C1C", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=4)
    tk.Button(prop_row, text="🧹 ล้างรูป", command=clear_prop_gallery, bg="#DC2626", fg="white", activebackground="#B91C1C", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=4)
    g["prop_page"] = prop_page
    return prop_page
