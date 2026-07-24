# -*- coding: utf-8 -*-
"""Image AI page source UI. Mirrors original pyc layout from screenshot."""
from __future__ import annotations

import tkinter as tk
import os
import re
from typing import Any, Dict
from snapgen_page_builder import (
    make_log_box, append_log, make_selection_lock_bar,
    set_selection_lock, remove_selection_lock,
)

BG = "#F5F5F2"
PANEL = "#FFFFFF"
BORDER = "#D9D9D9"
BLUE = "#2563EB"
PURPLE = "#7C3AED"
ORANGE = "#F59E0B"
RED = "#DC2626"
PINK = "#DB2777"
CYAN = "#0891B2"
GRAY = "#6B7280"


def _btn(parent, text, color, command=None, *, padx=12, pady=6, fg="white"):
    b = tk.Button(parent, text=text, command=command, bg=color, fg=fg,
                  activebackground=color, activeforeground=fg,
                  relief="flat", bd=0, cursor="hand2",
                  font=("Leelawadee UI", 9, "bold"), padx=padx, pady=pady)
    return b


def install(g: dict, root: tk.Misc) -> Dict[str, Any]:
    # Lock state belongs to this page only; never share it through global `g`.
    lock_g = {"_selection_locks": {}, "_selection_lock_vars": []}
    export_image_dir = g.get("EXPORT_IMAGE")
    page = tk.Frame(root, bg=BG)
    page.columnconfigure(0, weight=1)
    page.rowconfigure(5, weight=1)

    # Prompt panel
    prompt_frame = tk.LabelFrame(page, text="🎨 Prompt สร้างรูป (gpt-image-1)", bg=BG, fg="#111",
                                 padx=8, pady=8, bd=1, relief="solid")
    prompt_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 4))
    prompt_frame.columnconfigure(0, weight=1)

    # Keep Prompt compact so Log and Gallery remain visible on common screens.
    prompt_text = tk.Text(prompt_frame, height=6, wrap="word", bg=PANEL, fg="#111",
                          bd=1, relief="solid", font=("Leelawadee UI", 11), padx=8, pady=6)
    prompt_text.grid(row=0, column=0, sticky="ew")

    # Action bar like original screenshot
    bar = tk.Frame(page, bg=BG)
    bar.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 2))

    img_aspect_var = g.get("img_aspect_var") or tk.StringVar(value="16:9")
    img_lighting_var = g.get("img_lighting_var") or tk.StringVar(value="☀ กลางวัน")
    g["img_aspect_var"] = img_aspect_var
    g["img_lighting_var"] = img_lighting_var

    gen_btn = _btn(bar, "↻ สร้างรูป", BLUE, lambda: g["generate_image_standalone"](False), padx=16, pady=8)
    gen_btn.pack(side="left", padx=(0, 6))
    tk.Label(bar, text="ขนาด:", bg=BG).pack(side="left")
    tk.OptionMenu(bar, img_aspect_var, *(g.get("IMG_ASPECT_RATIOS") or ["16:9", "9:16", "1:1", "4:3", "3:4"])).pack(side="left", padx=(2, 8))
    tk.Label(bar, text="แสง:", bg=BG).pack(side="left")
    tk.OptionMenu(bar, img_lighting_var, *(list((g.get("LIGHTING_PRESETS") or {"☀ กลางวัน":"", "🌙 กลางคืน":""}).keys()))).pack(side="left", padx=(2, 8))
    prompt_btn = _btn(bar, "Prompt", PURPLE, lambda: (g.get("pick_prompt_for_image") or g.get("preview_and_insert_refs") or (lambda: None))())
    prompt_btn.pack(side="left", padx=3)
    storyboard_btn = _btn(bar, "Storyboard", ORANGE, lambda: (g.get("generate_storyboard_overview_image") or (lambda: None))())
    storyboard_btn.pack(side="left", padx=3)
    clear_btn = _btn(bar, "Clear", RED, lambda: (prompt_text.delete("1.0", tk.END), _schedule_ref_highlight(), (g.get("_img_log") or (lambda _m: None))("ล้าง prompt แล้ว")))
    clear_btn.pack(side="left", padx=3)
    autogen_btn = _btn(bar, "Auto-Gen", PINK, lambda: (g.get("auto_gen_queue") or (lambda: None))())
    autogen_btn.pack(side="left", padx=3)
    clear_gallery_btn = _btn(bar, "🧹 ล้างรูป", RED, lambda: (g.get("clear_gallery") or (lambda: None))())
    clear_gallery_btn.pack(side="left", padx=(12, 3))
    small_gen_btn = _btn(bar, "สร้างรูป", "#E5E7EB", lambda: _generate(False), fg="#111")
    small_gen_btn.pack(side="left", padx=3)

    # Ref row
    ref_row = tk.Frame(page, bg=BG)
    ref_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 4))
    ref_folder = g.get("img_ref_folder") or [None]
    ref_names_var = g.get("img_ref_names_var") or tk.StringVar(value="")
    ref_match_var = tk.StringVar(value="ใน prompt นี้ใช้ไฟล์แนบ 0 รูป")
    ref_label = tk.Label(ref_row, text="ไม่มีโฟลเดอร์อ้างอิง", fg="#555", bg=BG, anchor="w")
    choose_btn = _btn(ref_row, "📂 เลือกโฟลเดอร์อ้างอิง", ORANGE, g.get("browse_ref_folder"))
    choose_btn.pack(side="left", padx=(0, 8))
    ref_label.pack(side="left")
    tk.Label(ref_row, textvariable=ref_names_var, fg="#1565C0", bg=BG, anchor="w",
             font=("Leelawadee UI", 9)).pack(side="left", fill="x", expand=True, padx=(8, 0))
    tk.Label(ref_row, textvariable=ref_match_var, fg=PURPLE, bg=BG, anchor="e",
             font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=(8, 4))
    ref_clear_btn = _btn(ref_row, "X", RED, g.get("clear_ref_folder"), padx=8)
    ref_clear_btn.pack(side="right")

    lock_bar = make_selection_lock_bar(page, lock_g, bg=BG)
    lock_bar.grid(row=3, column=0, sticky="ew", padx=8, pady=(2, 2))
    g["img_lock_bar"] = lock_bar

    # Log panel
    log_frame = tk.LabelFrame(page, text="Log", bg=BG, padx=8, pady=8, bd=1, relief="solid")
    log_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(4, 4))
    log_frame.columnconfigure(0, weight=1)
    log_box = make_log_box(log_frame, bg=PANEL)
    log_box.grid(row=0, column=0, sticky="ew")

    # Gallery panel
    gallery_frame = tk.LabelFrame(page, text="แกลเลอรี", bg=BG, padx=8, pady=8, bd=1, relief="solid")
    gallery_frame.grid(row=5, column=0, sticky="nsew", padx=8, pady=(4, 8))
    gallery_frame.columnconfigure(0, weight=1)
    gallery_frame.rowconfigure(0, weight=1)
    gallery = tk.Canvas(gallery_frame, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
    scroll = tk.Scrollbar(gallery_frame, orient="vertical", command=gallery.yview)
    inner = tk.Frame(gallery, bg=PANEL)
    gallery_window = gallery.create_window((0, 0), window=inner, anchor="nw")
    gallery.configure(yscrollcommand=scroll.set)
    gallery.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")

    def _sync_gallery_scrollregion(_event=None):
        gallery.configure(scrollregion=gallery.bbox("all") or (0, 0, 0, 0))
        try:
            gallery.itemconfigure(gallery_window, width=max(gallery.winfo_width() - 4, 1))
        except Exception:
            pass

    def _gallery_on_mousewheel(event):
        # Scroll when the pointer is anywhere over the gallery area,
        # not only on the thin scrollbar.
        try:
            if not gallery.winfo_exists():
                return
            first, last = gallery.yview()
            if float(last) - float(first) >= 0.999:
                return
            delta = int(getattr(event, "delta", 0) or 0)
            if delta == 0:
                return
            gallery.yview_scroll(int(-1 * (delta / 120)), "units")
            return "break"
        except Exception:
            return

    def _bind_gallery_wheel(widget):
        try:
            widget.bind("<Enter>", lambda _e: gallery.bind_all("<MouseWheel>", _gallery_on_mousewheel), add="+")
            widget.bind("<Leave>", lambda _e: gallery.unbind_all("<MouseWheel>"), add="+")
            widget.bind("<MouseWheel>", _gallery_on_mousewheel, add="+")
        except Exception:
            pass

    inner.bind("<Configure>", _sync_gallery_scrollregion)
    gallery.bind("<Configure>", _sync_gallery_scrollregion)
    for _w in (gallery_frame, gallery, inner, scroll):
        _bind_gallery_wheel(_w)
    g["_bind_gallery_wheel"] = _bind_gallery_wheel
    g["_sync_gallery_scrollregion"] = _sync_gallery_scrollregion

    thumbs = []
    history = []
    busy = [False]
    first_row = [None]
    auto_gen_state = {"running": False, "cancel": False}

    def _notify_done():
        notify = g.get("_snapgen_notify_done")
        if callable(notify):
            try:
                notify()
            except Exception:
                pass

    manual_refs = []
    folder_ref_names = []

    def _log(msg):
        append_log(log_box, msg)

    def _resolve_portable_ref_folder(saved):
        """Resolve a saved reference folder after drive letters change."""
        if not saved:
            return ""
        original = Path(str(saved))
        if original.is_dir():
            return str(original)
        candidates = []
        try:
            # Google Drive commonly keeps the same path but receives another
            # drive letter on a different PC (G: -> H:, for example).
            parts = original.parts
            tail = Path(*parts[1:]) if original.drive and len(parts) > 1 else original
            if os.name == "nt":
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    candidates.append(Path(f"{letter}:/") / tail)
            project_root = Path(__file__).resolve().parent.parent
            candidates.extend([
                project_root / "export" / "ref" / original.name,
                project_root / "export" / "ref",
            ])
        except Exception:
            candidates = []
        for candidate in candidates:
            try:
                if candidate.is_dir():
                    return str(candidate)
            except Exception:
                pass
        return ""

    def _load_saved_ref_state():
        try:
            cfg = g.get("load_config", lambda: {})() or {}
            last_dirs = cfg.get("last_dirs") if isinstance(cfg.get("last_dirs"), dict) else {}
            saved_folder = last_dirs.get("image_ref") or cfg.get("ref_folder")
            folder = _resolve_portable_ref_folder(saved_folder)
            if folder:
                ref_folder[0] = folder
            saved_files = cfg.get("image_manual_refs") or []
            if isinstance(saved_files, list):
                restored = []
                for path in saved_files:
                    if os.path.isfile(str(path)):
                        restored.append(str(path))
                    elif folder:
                        moved = os.path.join(folder, os.path.basename(str(path)))
                        if os.path.isfile(moved):
                            restored.append(moved)
                manual_refs[:] = restored[:10]
            # Persist the repaired local path, or clear only this PC's stale
            # reference values so Repair does not warn forever.
            changed = bool(saved_folder and folder != str(saved_folder))
            if folder:
                last_dirs["image_ref"] = folder
                cfg["ref_folder"] = folder
            elif saved_folder:
                last_dirs.pop("image_ref", None)
                cfg.pop("ref_folder", None)
                changed = True
            cfg["last_dirs"] = last_dirs
            cfg["image_manual_refs"] = list(manual_refs)
            if changed:
                g.get("save_config", lambda _cfg: None)(cfg)
        except Exception as exc:
            _log(f"[ref] โหลดสถานะรูปอ้างอิงไม่ได้: {exc}")

    def _save_ref_state():
        try:
            cfg = g.get("load_config", lambda: {})() or {}
            last_dirs = cfg.get("last_dirs") if isinstance(cfg.get("last_dirs"), dict) else {}
            folder = ref_folder[0] if ref_folder and ref_folder[0] and os.path.isdir(ref_folder[0]) else ""
            if folder:
                last_dirs["image_ref"] = folder
                cfg["ref_folder"] = folder
            else:
                last_dirs.pop("image_ref", None)
                cfg.pop("ref_folder", None)
            cfg["last_dirs"] = last_dirs
            cfg["image_manual_refs"] = [str(path) for path in manual_refs if os.path.isfile(str(path))][:10]
            g.get("save_config", lambda _cfg: None)(cfg)
        except Exception as exc:
            _log(f"[ref] บันทึกสถานะรูปอ้างอิงไม่ได้: {exc}")

    _load_saved_ref_state()
    if ref_folder[0] and os.path.isdir(ref_folder[0]):
        try:
            _restored_images = [
                name for name in os.listdir(ref_folder[0])
                if os.path.splitext(name)[1].lower() in (".png", ".jpg", ".jpeg", ".webp")
            ]
            ref_label.config(
                text=f"{os.path.basename(ref_folder[0])} ({len(_restored_images)} รูป)",
                fg="#333",
            )
            ref_names_var.set(", ".join(os.path.splitext(name)[0] for name in _restored_images))
            folder_ref_names[:] = [os.path.splitext(name)[0] for name in _restored_images]
            for name in folder_ref_names:
                set_selection_lock(lock_g, "reference", name, append=True)
        except Exception as exc:
            _log(f"[ref] แสดงโฟลเดอร์อ้างอิงเดิมไม่ได้: {exc}")
    for _restored_ref in manual_refs:
        set_selection_lock(
            lock_g, "reference", os.path.splitext(os.path.basename(_restored_ref))[0], append=True,
        )

    _REF_HL_COLORS = ("#7C3AED", "#2563EB", "#DB2777", "#0891B2", "#F59E0B")
    _ref_preview_after = [None]

    def _list_ref_files():
        out = []
        seen = set()
        folder = ref_folder[0] if ref_folder else None
        if folder and os.path.isdir(folder):
            try:
                for fn in sorted(os.listdir(folder)):
                    if os.path.splitext(fn)[1].lower() in (".png", ".jpg", ".jpeg", ".webp"):
                        path = os.path.join(folder, fn)
                        stem = os.path.splitext(fn)[0]
                        if path not in seen:
                            seen.add(path)
                            out.append((stem, path))
            except Exception:
                pass
        for path in manual_refs:
            if path and path not in seen and os.path.exists(path):
                seen.add(path)
                out.append((os.path.splitext(os.path.basename(path))[0], path))
        return out

    def _matching_ref_files_for_text(text):
        prompt = str(text or "").lower()
        matched = []
        for stem, path in _list_ref_files():
            key = str(stem).strip()
            if len(key) >= 2 and key.lower() in prompt:
                matched.append((key, path))
        return matched

    def _matching_ref_files():
        return _matching_ref_files_for_text(prompt_text.get("1.0", tk.END))

    def _update_ref_highlight(log=False):
        try:
            for tag in prompt_text.tag_names():
                if str(tag).startswith("ref_word_hl_"):
                    prompt_text.tag_delete(tag)
        except Exception:
            pass

        matched = _matching_ref_files()
        total_hits = 0
        for i, (name, _path) in enumerate(sorted(matched, key=lambda x: len(x[0]), reverse=True)):
            color = _REF_HL_COLORS[i % len(_REF_HL_COLORS)]
            tag = "ref_word_hl_" + re.sub(r"\W+", "_", name, flags=re.UNICODE)
            try:
                prompt_text.tag_config(tag, foreground=color, background="#F3E8FF")
                start = "1.0"
                while True:
                    pos = prompt_text.search(name, start, stopindex=tk.END, nocase=True)
                    if not pos:
                        break
                    end = pos + f"+{len(name)}c"
                    prompt_text.tag_add(tag, pos, end)
                    total_hits += 1
                    start = end
            except Exception:
                pass

        count = len(matched)
        if count:
            names = ", ".join(name for name, _ in matched[:8])
            ref_match_var.set(f"ใน prompt นี้ใช้ไฟล์แนบ {count} รูป: {names}")
            if log:
                _log(f"[ref] ใช้ไฟล์แนบ {count} รูป: {names}")
        else:
            ref_match_var.set("ใน prompt นี้ใช้ไฟล์แนบ 0 รูป")
            if log:
                _log("[ref] ใน prompt นี้ยังไม่เจอชื่อไฟล์แนบ")
        return count, total_hits

    def _schedule_ref_highlight(_event=None):
        try:
            old = _ref_preview_after[0]
            if old:
                root.after_cancel(old)
        except Exception:
            pass
        _ref_preview_after[0] = root.after(180, _update_ref_highlight)

    g["highlight_matched_words"] = lambda: _update_ref_highlight(log=True)
    g["auto_update_ref_preview"] = _schedule_ref_highlight
    try:
        prompt_text.bind("<KeyRelease>", _schedule_ref_highlight, add="+")
        prompt_text.bind("<<Modified>>", lambda _e: (prompt_text.edit_modified(False), _schedule_ref_highlight()), add="+")
    except Exception:
        pass

    def _gallery_add(path):
        import os
        import subprocess
        row = tk.Frame(inner, bg=PANEL, bd=1, relief="groove", padx=4, pady=4)
        if first_row[0] and first_row[0].winfo_exists():
            row.pack(fill="x", pady=2, before=first_row[0])
            first_row[0] = row
        else:
            row.pack(fill="x", pady=2)
            first_row[0] = row

        photo = None
        try:
            from PIL import Image, ImageTk
            pil = Image.open(path)
            pil.thumbnail((160, 110))
            photo = ImageTk.PhotoImage(pil)
            thumbs.append(photo)
        except Exception:
            pass

        thumb = tk.Frame(row, bg=PANEL, width=170, height=116)
        thumb.pack(side="left", padx=(0, 8))
        thumb.pack_propagate(False)
        if photo:
            tk.Label(thumb, image=photo, bg=PANEL).pack(expand=True)
        else:
            tk.Label(thumb, text="ไม่มี preview", bg=PANEL, fg="#9CA3AF").pack(expand=True)

        tk.Label(row, text=os.path.basename(str(path)), bg=PANEL, fg="#111",
                 anchor="w", wraplength=420).pack(side="left", fill="x", expand=True, padx=6)

        btns = tk.Frame(row, bg=PANEL)
        btns.pack(side="right")
        def open_image(p=path):
            target = os.path.normpath(str(p))
            try:
                os.startfile(target)  # open image with default viewer
            except Exception as exc:
                _log(f"เปิดรูปไม่สำเร็จ: {exc}")

        tk.Button(btns, text="📂 เปิด", command=open_image).pack(fill="x")
        slotrow = tk.Frame(btns, bg=PANEL)
        slotrow.pack(fill="x")

        def send(slot, p=path):
            fn = g.get("load_slot_image")
            if not callable(fn):
                _log("ไม่พบปุ่มส่งเข้า Slot จากหน้า Video")
                return
            try:
                fn(slot, p, skip_sidecar=True)
            except TypeError:
                fn(slot, p)

            # Fill the matching Video Prompt here, in the actual button
            # callback.  Do not depend on load_slot_image being wrapped: the
            # recovered Video page and adapters can replace that callable at
            # different points during startup.
            matched_prompt = False
            matcher = g.get("video_prompt_for_image_path")
            if callable(matcher):
                try:
                    prompt_no, video_prompt, reason = matcher(p, fallback_slot=None)
                    boxes = g.get("slot_prompts") or []
                    if video_prompt and 0 <= int(slot) < len(boxes):
                        box = boxes[int(slot)]
                        box.delete("1.0", tk.END)
                        box.insert("1.0", video_prompt)
                        matched_prompt = True
                        _log(f"[slot] รูปนี้ตรงกับ Prompt {prompt_no} — ใส่ Video Prompt {prompt_no} แล้ว ({reason})")
                except Exception as exc:
                    _log(f"[slot] จับคู่ Prompt ไม่สำเร็จ: {exc}")
            if not matched_prompt:
                _log(f"[slot] ส่งรูปไป Slot {slot + 1} แล้ว แต่ไม่พบ Prompt ต้นทางของรูป")
            switch = g.get("switch_mode")
            if callable(switch):
                try:
                    root.after(80, lambda: switch("video"))
                except Exception:
                    try:
                        switch("video")
                    except Exception:
                        pass

        for i in range(2):
            tk.Button(slotrow, text=f"Slot {i + 1}", width=6, bg="#C8E6C9",
                      command=lambda i=i: send(i)).pack(side="left", padx=1)
        # Keep mouse-wheel scrolling active over every gallery row widget.
        bind_wheel = g.get("_bind_gallery_wheel")
        if callable(bind_wheel):
            for widget in (row, thumb, btns, slotrow):
                bind_wheel(widget)
            for child in list(row.winfo_children()) + list(btns.winfo_children()) + list(slotrow.winfo_children()):
                bind_wheel(child)
        sync = g.get("_sync_gallery_scrollregion")
        if callable(sync):
            try:
                sync()
            except Exception:
                pass
        history.insert(0, path)
        _schedule_ref_highlight()

    def _prompt_entries():
        loader = g.get("load_prompt_bank_entries_by_mode")
        if callable(loader):
            return [(k, p) for k, p in loader("image") if str(p).strip()]
        return []

    def _is_storyboard_prompt(key, prompt):
        text = f"{key or ''}\n{prompt or ''}"
        return bool(re.search(r"(?i)storyboard|รวม\s*ซีน|ภาพรวม|single\s+image\s+storyboard|panel|grid", text))

    def _scene_prompts_only(entries):
        scenes = []
        for key, prompt in entries:
            prompt = str(prompt).strip()
            if prompt and not _is_storyboard_prompt(key, prompt):
                scenes.append(prompt)
        return scenes

    def _storyboard_prompt_from_entries(entries):
        for key, prompt in reversed(entries):
            prompt = str(prompt).strip()
            if prompt and _is_storyboard_prompt(key, prompt):
                return prompt
        prompts = [str(p).strip() for _k, p in entries if str(p).strip()]
        return prompts[-1] if prompts else ""

    def _pick_prompt():
        entries = _prompt_entries()
        win = tk.Toplevel(root)
        win.title("เลือก Prompt - สร้างรูป")
        win.geometry("820x620")
        win.minsize(760, 500)
        win.configure(bg="#FFFFFF")
        accent = PURPLE
        accent_soft = "#F3E8FF"
        neutral = "#E5E7EB"
        neutral_text = "#111827"
        try:
            win.transient(root)
        except Exception:
            pass

        wrap = tk.Frame(win, bg="#FFFFFF")
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(wrap, text=f"พบ {len(entries)} prompts — เลื่อนดูลงมาได้ทีละกล่อง",
                 bg="#FFFFFF", fg="#555", font=("Leelawadee UI", 10)).pack(anchor="w", pady=(0, 6))

        canvas = tk.Canvas(wrap, bg="#FFFFFF", highlightthickness=0)
        scroll = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#FFFFFF")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        selected = {"idx": 0}
        selected_label = tk.StringVar(value=(entries[0][0] if entries else "ไม่มี prompt"))
        cards = []

        def choose(idx):
            if not entries:
                return
            selected["idx"] = idx
            selected_label.set(entries[idx][0])
            for j, card in enumerate(cards):
                active = j == idx
                bg = accent_soft if active else "#FFFFFF"
                card.config(bg=bg, relief=("ridge" if active else "groove"))
                for child in card.winfo_children():
                    try:
                        child.config(bg=bg)
                    except Exception:
                        pass

        for i, (key, prompt_body) in enumerate(entries):
            card = tk.Frame(inner, bd=1, relief="groove", bg="#FFFFFF", padx=8, pady=6)
            card.pack(fill="x", padx=2, pady=4)
            cards.append(card)
            tk.Label(card, text=f"#{i + 1}  {key}", anchor="w", bg="#FFFFFF",
                     fg="#111", font=("Leelawadee UI", 10, "bold")).pack(fill="x")
            msg = tk.Message(card, text=prompt_body, width=720, bg="#FFFFFF",
                             fg="#111", font=("Leelawadee UI", 10))
            msg.pack(fill="x", pady=(3, 0))
            for widget in (card, msg):
                widget.bind("<Button-1>", lambda _e, idx=i: choose(idx))
                widget.bind("<Double-Button-1>", lambda _e, idx=i: (choose(idx), use()))

        if not entries:
            tk.Label(inner, text="ไม่มี prompt ใน prompt_bank.txt", bg="#FFFFFF",
                     fg="#666", font=("Leelawadee UI", 11)).pack(anchor="w", padx=8, pady=16)

        def on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        def use():
            if not entries:
                (g.get("show_error") or (lambda _t, _m: _log(_m)))("Prompt", "ไม่มี prompt ใน prompt_bank.txt")
                return
            _key, chosen_prompt = entries[selected["idx"]]
            prompt_text.delete("1.0", tk.END)
            prompt_text.insert("1.0", chosen_prompt)
            _log(set_selection_lock(lock_g, "prompt", _key))
            fn = g.get("auto_update_ref_preview")
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
            close()

        def close():
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
            win.destroy()

        canvas.bind_all("<MouseWheel>", on_wheel)

        bottom = tk.Frame(win, bg="#FFFFFF")
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(bottom, textvariable=selected_label, anchor="w", bg="#FFFFFF",
                 fg="#111", font=("Leelawadee UI", 10)).pack(side="left", fill="x", expand=True)
        tk.Button(bottom, text="Use", command=use, bg=accent, fg="white",
                  activebackground=accent, activeforeground="white",
                  relief="flat", bd=0, padx=14, pady=6,
                  font=("Leelawadee UI", 9, "bold")).pack(side="right", padx=(6, 0))
        tk.Button(bottom, text="Close", command=close, bg=neutral, fg=neutral_text,
                  activebackground=neutral, activeforeground=neutral_text,
                  relief="flat", bd=0, padx=14, pady=6,
                  font=("Leelawadee UI", 9, "bold")).pack(side="right")

        win.protocol("WM_DELETE_WINDOW", close)
        if entries:
            choose(0)
        try:
            win.update_idletasks()
            x = root.winfo_rootx() + max(0, (root.winfo_width() - win.winfo_width()) // 2)
            y = root.winfo_rooty() + max(0, (root.winfo_height() - win.winfo_height()) // 2)
            win.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _generate(is_edit=False, prompt_override=None, name_hint=None, prompt_index=None):
        prompt = (prompt_override or prompt_text.get("1.0", tk.END)).strip()
        if not prompt:
            (g.get("show_error") or (lambda _t, _m: _log(_m)))("สร้างรูป", "ใส่ prompt ก่อน")
            return
        # The Prompt picker previously copied only the text into the editor.
        # A normal click on "สร้างรูป" therefore lost its Image Slot number,
        # so Video could not know which matching prompt to load.  Resolve the
        # exact source here for every generation path, including pasted text
        # that exactly matches an entry in the image prompt bank.
        if prompt_index is None:
            normalized = re.sub(r"\s+", " ", prompt).strip()
            for entry_pos, (entry_key, entry_prompt) in enumerate(_prompt_entries(), 1):
                if re.sub(r"\s+", " ", str(entry_prompt)).strip() != normalized:
                    continue
                match = re.search(r"(\d{1,3})", str(entry_key or ""))
                prompt_index = int(match.group(1)) if match else entry_pos
                break
        if busy[0]:
            _log("กำลังสร้างรูปอยู่ — รอให้งานเดิมเสร็จก่อน")
            return
        matched_refs = _matching_ref_files()
        prompt_lock_name = str(name_hint or (f"Prompt {prompt_index}" if prompt_index else prompt[:45])).strip()
        set_selection_lock(lock_g, "prompt", prompt_lock_name)
        for ref_name, _ref_path in matched_refs:
            set_selection_lock(lock_g, "reference", ref_name, append=True)
        busy[0] = True
        gen_btn.config(state="disabled")
        try: small_gen_btn.config(state="disabled")
        except Exception: pass
        _log(f"กำลังสร้างรูป... ใช้ไฟล์แนบ {len(matched_refs)} รูป" if matched_refs else "กำลังสร้างรูป... ไม่เจอชื่อไฟล์แนบใน prompt")
        def worker():
            try:
                do_req = g.get("_do_image_request")
                if not do_req: raise RuntimeError("_do_image_request missing")
                payload = {"prompt": prompt, "aspect_ratio": img_aspect_var.get()}
                ref_paths = [p for _name, p in matched_refs]
                if not ref_paths and manual_refs:
                    ref_paths = list(manual_refs)
                if ref_paths:
                    enc = g.get("_encode_image_b64")
                    if enc: payload["images"] = [enc(p) for p in ref_paths[:10]]
                out = do_req(payload, is_edit=bool(payload.get("images")), prompt=prompt, name_hint=name_hint or prompt, raw_prompt=prompt, prompt_index=prompt_index, output_dir=str(export_image_dir) if export_image_dir else None)
                root.after(0, lambda p=out: (_gallery_add(p), _log("สร้างรูปเสร็จ"), _notify_done()))
            except Exception as e:
                root.after(0, lambda m=str(e): _log("❌ " + m))
            finally:
                def release():
                    busy[0] = False
                    gen_btn.config(state="normal")
                    try: small_gen_btn.config(state="normal")
                    except Exception: pass
                root.after(0, release)
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _storyboard():
        entries = _prompt_entries(); prompts = [p for _k, p in entries]
        sb = next((p for p in prompts if "Storyboard" in p or "รวมซีน" in p), prompts[-1] if prompts else prompt_text.get("1.0", tk.END).strip())
        prompt_text.delete("1.0", tk.END); prompt_text.insert("1.0", sb)
        _generate(False, sb, "storyboard", 11)

    def _matched_refs_for_prompt(prompt):
        return _matching_ref_files_for_text(prompt)

    def _build_image_payload(base_prompt, ref_paths=None, scene_index=None, scene_total=None):
        aspect = img_aspect_var.get()
        lighting = ""
        presets = g.get("LIGHTING_PRESETS") or {}
        try:
            lighting = presets.get(img_lighting_var.get(), "")
        except Exception:
            lighting = ""
        lock = ""
        quality = "Photorealistic, ultra detailed, sharp focus, high resolution, crisp edges, professional photography quality."
        prefix = ""
        if scene_index is not None and scene_total is not None:
            prefix = (
                f"นี่คือเหตุการณ์ที่ {scene_index} จากทั้งหมด {scene_total}. "
                if scene_index <= 1 else
                f"นี่คือเหตุการณ์ที่ {scene_index} จากทั้งหมด {scene_total} ต่อจากเหตุการณ์ {scene_index - 1}. "
            )
        full = prefix + base_prompt.rstrip(".") + f". Use {aspect} aspect ratio composition. {lock} {quality} {lighting}."
        payload = {"prompt": full, "aspect_ratio": aspect, "history_and_training_disabled": False}
        if ref_paths:
            enc = g.get("_encode_image_b64")
            if enc:
                payload["images"] = [enc(p) for p in ref_paths[:10]]
        return payload, full

    def _auto_gen():
        if auto_gen_state["running"]:
            auto_gen_state["cancel"] = True
            _log("[auto] สั่งหยุดคิวแล้ว — รอรูปปัจจุบันเสร็จก่อน")
            return
        entries = _prompt_entries()
        if not entries:
            (g.get("show_error") or (lambda _t, _m: _log(_m)))("Auto-Gen", "ไม่มี prompt ใน prompt_bank.txt")
            return
        prompts = _scene_prompts_only(entries)
        if not prompts:
            _log("ไม่มี prompt ซีนใน prompt_bank.txt")
            return
        total = len(prompts)

        sel_win = tk.Toplevel(root)
        sel_win.title("เลือกช่วง Auto-Gen")
        sel_win.geometry("340x220")
        sel_win.configure(bg="#FFFFFF")
        try:
            sel_win.transient(root)
        except Exception:
            pass
        tk.Label(sel_win, text=f"มี {total} ซีน — ไม่รวม Storyboard", bg="#FFFFFF", fg="#333",
                 font=("Leelawadee UI", 10, "bold")).pack(pady=10)
        rng_frame = tk.Frame(sel_win, bg="#FFFFFF")
        rng_frame.pack(pady=4)
        from_val = tk.IntVar(value=1)
        to_val = tk.IntVar(value=total)
        tk.Label(rng_frame, text="จาก", bg="#FFFFFF").pack(side="left", padx=4)
        tk.OptionMenu(rng_frame, from_val, *range(1, total + 1)).pack(side="left")
        tk.Label(rng_frame, text="ถึง", bg="#FFFFFF").pack(side="left", padx=4)
        tk.OptionMenu(rng_frame, to_val, *range(1, total + 1)).pack(side="left")

        def start_queue():
            start_n = from_val.get()
            end_n = to_val.get()
            if start_n > end_n:
                start_n, end_n = end_n, start_n
            sel_win.destroy()
            queue_nums = list(range(start_n, end_n + 1))
            auto_gen_state["running"] = True
            auto_gen_state["cancel"] = False
            autogen_btn.config(text="หยุด Auto-Gen", bg=RED)
            gen_btn.config(state="disabled")
            try: small_gen_btn.config(state="disabled")
            except Exception: pass
            _log(f"[auto] เริ่ม — สร้าง Storyboard ก่อน แล้วซีน {start_n}-{end_n} จาก {total} ซีน (ไม่รวม Storyboard)")

            def finish(done, total_count):
                auto_gen_state["running"] = False
                auto_gen_state["cancel"] = False
                autogen_btn.config(text="Auto-Gen", bg=PINK)
                gen_btn.config(state="normal")
                try: small_gen_btn.config(state="normal")
                except Exception: pass
                _log(f"[auto] เสร็จทั้งหมด — {done}/{total_count} ซีน")
                _notify_done()

            def worker():
                do_req = g.get("_do_image_request")
                if not callable(do_req):
                    root.after(0, lambda: (_log("❌ _do_image_request missing"), finish(0, len(queue_nums))))
                    return

                storyboard_path = None
                try:
                    sb_prompt = _storyboard_prompt_from_entries(entries)
                    if sb_prompt:
                        root.after(0, lambda: _log("[auto] Storyboard reference กำลังสร้าง..."))
                        sb_refs = [p for _name, p in _matched_refs_for_prompt(sb_prompt)]
                        for p in manual_refs:
                            if p not in sb_refs and os.path.exists(p):
                                sb_refs.append(p)
                        payload, full = _build_image_payload(sb_prompt, sb_refs)
                        lock = g.get("_bridge_queue_lock")
                        if lock:
                            with lock:
                                wait = g.get("_wait_bridge_free")
                                if callable(wait):
                                    wait(log_fn=_log)
                                storyboard_path = do_req(payload, is_edit=bool(sb_refs), prompt=full, name_hint=sb_prompt, raw_prompt=sb_prompt, prompt_index=11, output_dir=str(export_image_dir) if export_image_dir else None)
                        else:
                            storyboard_path = do_req(payload, is_edit=bool(sb_refs), prompt=full, name_hint=sb_prompt, raw_prompt=sb_prompt, prompt_index=11, output_dir=str(export_image_dir) if export_image_dir else None)
                        root.after(0, lambda p=storyboard_path: (_gallery_add(p), _log(f"[auto] Storyboard เสร็จ: {os.path.basename(str(p))}")))
                except Exception as e:
                    root.after(0, lambda m=str(e): _log(f"[auto] Storyboard error: {m} — ดำเนินต่อ"))
                    storyboard_path = None

                done = 0
                prev_path = None
                for n in queue_nums:
                    if auto_gen_state["cancel"]:
                        root.after(0, lambda done=done: _log(f"[auto] หยุดแล้ว — เสร็จ {done}/{len(queue_nums)} ซีน"))
                        break
                    p = prompts[n - 1]
                    root.after(0, lambda n=n, p=p: (
                        prompt_text.delete("1.0", tk.END),
                        prompt_text.insert("1.0", p),
                        _update_ref_highlight(),
                        _log(f"[auto] ซีน {n}/{queue_nums[-1]} — กำลังสร้าง...")
                    ))
                    try:
                        ref_paths = [path for _name, path in _matched_refs_for_prompt(p)]
                        for extra in (storyboard_path, prev_path):
                            if extra and os.path.exists(extra) and extra not in ref_paths:
                                ref_paths.insert(0 if extra == storyboard_path else min(1, len(ref_paths)), extra)
                        for extra in manual_refs:
                            if extra and os.path.exists(extra) and extra not in ref_paths:
                                ref_paths.append(extra)
                        payload, full = _build_image_payload(p, ref_paths[:10], scene_index=n, scene_total=total)
                        lock = g.get("_bridge_queue_lock")
                        if lock:
                            with lock:
                                wait = g.get("_wait_bridge_free")
                                if callable(wait):
                                    wait(log_fn=_log)
                                out = do_req(payload, is_edit=bool(ref_paths), prompt=full, name_hint=p, raw_prompt=p, prompt_index=n, output_dir=str(export_image_dir) if export_image_dir else None)
                        else:
                            out = do_req(payload, is_edit=bool(ref_paths), prompt=full, name_hint=p, raw_prompt=p, prompt_index=n, output_dir=str(export_image_dir) if export_image_dir else None)
                        prev_path = out
                        done += 1
                        root.after(0, lambda out=out, n=n: (_gallery_add(out), _log(f"[auto] ซีน {n} เสร็จ: {os.path.basename(str(out))}")))
                    except Exception as e:
                        done += 1
                        root.after(0, lambda m=str(e), n=n: _log(f"[auto] ❌ ซีน {n} error: {m}"))
                root.after(0, lambda done=done: finish(done, len(queue_nums)))

            import threading
            threading.Thread(target=worker, daemon=True).start()

        tk.Button(sel_win, text="เริ่ม Auto-Gen", command=start_queue, bg=PINK, fg="white",
                  relief="flat", padx=18, pady=7, font=("Leelawadee UI", 9, "bold")).pack(pady=8)
        tk.Button(sel_win, text="ยกเลิก", command=sel_win.destroy, bg="#E5E7EB", fg="#111",
                  relief="flat", padx=18, pady=7, font=("Leelawadee UI", 9, "bold")).pack(pady=4)

    def _attach_refs():
        from tkinter import filedialog
        files = filedialog.askopenfilenames(title="แนบรูป", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        for old in manual_refs:
            remove_selection_lock(lock_g, "reference", os.path.splitext(os.path.basename(old))[0])
        manual_refs[:] = list(files)[:10]
        for path in manual_refs:
            set_selection_lock(lock_g, "reference", os.path.splitext(os.path.basename(path))[0], append=True)
        _save_ref_state()
        _log(f"ล็อกไฟล์แนบแล้ว {len(manual_refs)} รูป")
        _update_ref_highlight(log=True)

    def _clear_refs():
        for old in manual_refs:
            remove_selection_lock(lock_g, "reference", os.path.splitext(os.path.basename(old))[0])
        manual_refs.clear(); _save_ref_state(); _log("ล้างรูปแนบแล้ว"); _update_ref_highlight()

    def _clear_gallery():
        """Clear only the on-screen gallery. Real files stay in export/image."""
        for w in list(inner.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        thumbs.clear()
        history.clear()
        first_row[0] = None
        try:
            gallery.yview_moveto(0)
            sync = g.get("_sync_gallery_scrollregion")
            if callable(sync):
                sync()
            else:
                gallery.configure(scrollregion=gallery.bbox("all") or (0, 0, 0, 0))
        except Exception:
            pass
        _log("ล้าง gallery แล้ว — ไฟล์จริงยังอยู่ใน export/image")

    def _browse_ref_folder():
        from tkinter import filedialog
        import os
        d = filedialog.askdirectory(title="เลือกโฟลเดอร์อ้างอิง")
        if not d: return
        ref_folder[0] = d
        imgs = [f for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        ref_label.config(text=f"{os.path.basename(d)} ({len(imgs)} รูป)", fg="#333")
        ref_names_var.set(", ".join(os.path.splitext(x)[0] for x in imgs))
        for old in folder_ref_names:
            remove_selection_lock(lock_g, "reference", old)
        folder_ref_names[:] = [os.path.splitext(x)[0] for x in imgs]
        for name in folder_ref_names:
            set_selection_lock(lock_g, "reference", name, append=True)
        _save_ref_state()
        _log(f"[ref] ล็อกโฟลเดอร์ {os.path.basename(d)} — {len(imgs)} รูป")
        _update_ref_highlight(log=True)

    def _clear_ref_folder():
        for old in folder_ref_names:
            remove_selection_lock(lock_g, "reference", old)
        folder_ref_names.clear()
        ref_folder[0] = None; _save_ref_state(); ref_label.config(text="ไม่มีโฟลเดอร์อ้างอิง", fg="#555"); ref_names_var.set(""); _log("ล้างโฟลเดอร์อ้างอิงแล้ว"); _update_ref_highlight()

    gen_btn.config(command=lambda: _generate(False))
    try: small_gen_btn.config(command=lambda: _generate(False))
    except Exception: pass
    prompt_btn.config(command=_pick_prompt)
    storyboard_btn.config(command=_storyboard)
    autogen_btn.config(command=_auto_gen)
    clear_gallery_btn.config(command=_clear_gallery)
    choose_btn.config(command=_browse_ref_folder)
    ref_clear_btn.config(command=_clear_ref_folder)
    g["clear_gallery"] = _clear_gallery

    # Restore recent generated images after reopening the app.  Besides being
    # useful to the user, this guarantees that a fixed Slot callback can be
    # used immediately without regenerating (and spending quota) just to get
    # the gallery buttons back.
    try:
        if export_image_dir and os.path.isdir(str(export_image_dir)):
            recent_images = [
                os.path.join(str(export_image_dir), name)
                for name in os.listdir(str(export_image_dir))
                if os.path.splitext(name)[1].lower() in (".png", ".jpg", ".jpeg", ".webp")
            ]
            recent_images.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            for old_path in reversed(recent_images[:20]):
                _gallery_add(old_path)
    except Exception as exc:
        _log(f"โหลดรูปเดิมใน Gallery ไม่สำเร็จ: {exc}")

    # Export same global names overlay expects.
    g.update({
        "img_page": page,
        "img_prompt_frame": prompt_frame,
        "img_prompt_text": prompt_text,
        "img_btn_row": bar,
        "img_gen_btn": gen_btn,
        "img_edit_btn": None,
        "img_preview_refs_btn": None,
        "img_status_var": tk.StringVar(value="พร้อมสร้างรูป"),
        "img_ref_row": ref_row,
        "img_ref_label": ref_label,
        "img_ref_folder": ref_folder,
        "img_ref_names_var": ref_names_var,
        "img_ref_match_var": ref_match_var,
        "img_gallery_frame": gallery_frame,
        "img_gallery": gallery,
        "img_gallery_inner": inner,
        "img_gallery_add": _gallery_add,
        "img_gallery_thumbs": thumbs,
        "img_history": history,
        "img_busy": busy,
        "img_gallery_first_row": first_row,
        "image_action_buttons": [gen_btn, small_gen_btn, prompt_btn, storyboard_btn, autogen_btn, clear_gallery_btn],
    })
    return {"page": page, "prompt_text": prompt_text, "gallery_inner": inner, "log_box": log_box}
