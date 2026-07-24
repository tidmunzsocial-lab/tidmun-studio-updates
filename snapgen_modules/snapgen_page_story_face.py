# -*- coding: utf-8 -*-
"""SnapGen story face page.

This module owns the widgets, state, and callbacks for this page only.
"""
from __future__ import annotations

import json
import re
import urllib.request
import tkinter as tk
from snapgen_page_builder import (
    make_log_box as _builder_make_log_box,
    append_log as _builder_append_log,
    make_selection_lock_bar as _builder_make_selection_lock_bar,
    set_selection_lock as _builder_set_selection_lock,
)


def install(g: dict, root: tk.Misc) -> tk.Misc:
    """Build this page and return its root frame."""
    globals().update(g)
    lock_g = {"_selection_locks": {}, "_selection_lock_vars": []}
    export_story_face_dir = g.get("EXPORT_STORY_FACE", BASE / "story_face")
    new_page = tk.Frame(root, bg="#FAFAF7")
    g["new_page"] = new_page
    new_name_var = tk.StringVar(value="")
    g["new_name_var"] = new_name_var

    def _notify_done():
        notify = g.get("_snapgen_notify_done")
        if callable(notify):
            try:
                notify()
            except Exception:
                pass
    
    new_box = tk.LabelFrame(new_page, text="👤 นิทาน — ใบหน้าตัวละคร", bg="#FAFAF7", fg="#1A1A1A", padx=10, pady=8)
    new_box.pack(fill="x", padx=10, pady=10)
    new_row = tk.Frame(new_box, bg="#FAFAF7")
    new_row.pack(fill="x")
    tk.Label(new_row, text="ชื่อ:", bg="#FAFAF7", fg="#333").pack(side="left")
    new_entry_wrap = tk.Frame(new_row, bg="#FFFFFF", highlightthickness=1, highlightbackground="#D1D5DB")
    new_entry_wrap.pack(side="left", fill="x", expand=True, padx=6)
    new_entry = tk.Entry(new_entry_wrap, textvariable=new_name_var, relief="flat", bg="#FFFFFF", fg="#111")
    new_entry.pack(fill="x", padx=8, pady=6)
    new_placeholder = tk.Label(new_entry_wrap, text="ใส่ชื่อ", bg="#FFFFFF", fg="#B0B0B0", font=("Leelawadee UI", 9))
    new_placeholder.place(x=10, y=6)
    
    # Age dropdown (วัย)
    new_age_var = tk.StringVar(value="อัตโนมัติ")
    g["new_age_var"] = new_age_var
    _FACE_AGES = ("อัตโนมัติ", "เด็ก", "วัยรุ่น", "ผู้ใหญ่", "ผู้สูงอายุ")
    _FACE_AGE_MAP = {"อัตโนมัติ": "auto", "เด็ก": "8", "วัยรุ่น": "17", "ผู้ใหญ่": "35", "ผู้สูงอายุ": "65"}
    g["_FACE_AGE_MAP"] = _FACE_AGE_MAP
    tk.Label(new_row, text="วัย:", bg="#FAFAF7", fg="#333").pack(side="left", padx=(8, 0))
    new_age_menu = tk.OptionMenu(new_row, new_age_var, *_FACE_AGES)
    new_age_menu.config(relief="flat", bg="#FFFFFF", fg="#111", font=("Leelawadee UI", 9), highlightthickness=1, highlightbackground="#D1D5DB")
    new_age_menu.pack(side="left", padx=4)
    g["new_age_menu"] = new_age_menu
    
    new_select_btn = tk.Button(new_row, text="Select", command=lambda: None, bg="#2563EB", fg="white", activebackground="#1D4ED8", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold"))
    g["story_face_select_btn"] = new_select_btn
    
    def _sync_new_placeholder(*_):
        try:
            if new_name_var.get().strip():
                new_placeholder.place_forget()
            else:
                new_placeholder.place(x=10, y=6)
        except Exception:
            pass
    
    new_name_var.trace_add("write", _sync_new_placeholder)
    new_entry.bind("<FocusIn>", lambda _e: _sync_new_placeholder(), add="+")
    
    story_face_prompt = (
        "Close-up face portrait of a Thai character named {name}, {age} years old. "
        "Distinct non-generic identity with age-accurate face shape, eyes, eyebrows, nose, lips, jaw and cheekbones. "
        "Head-and-shoulders, full front-facing, centered, looking straight at camera, neutral expression. "
        "Mouth fully closed with relaxed closed lips; absolutely no visible teeth, no open mouth, no smile. "
        "Hair fully pulled and secured behind the head; absolutely no bangs or loose strands covering the forehead, "
        "temples, eyebrows, cheeks, jawline or ears. Full hairline and both ears visible. 85mm portrait lens. "
        "Age-accurate unretouched skin microdetail: visible pores, fine lines, wrinkles, crow's-feet, nasolabial folds, "
        "spots, freckles, moles, scars and uneven texture where appropriate. Older faces show pronounced authentic age "
        "lines. No beauty filter, no airbrushing, no waxy, porcelain, plastic or excessively smooth skin. "
        "Shadowless color-calibrated white studio lighting at neutral D55 white balance: two identical extra-large "
        "softboxes symmetrically left and right with equal height, angle, distance and power, plus centered on-axis fill. "
        "Both sides of the face have identical brightness and color, less than 5 percent luminance difference. Uniform "
        "exposure forehead to neck, flat neutral albedo appearance. Pure neutral light-gray background. No yellow, orange "
        "or warm cast, no sepia, green or blue cast, no directional key, side, rim, back or dramatic light, no dark half "
        "of face, no highlight gradient, no cinematic color grading. Tack-sharp 85mm micro-focus with high local contrast, crisp pores and skin texture, no soft blur, no diffusion filter, no plastic smoothing. Photorealistic, color-accurate skin, 3:4 portrait."
    )
    g["story_face_prompt_template"] = story_face_prompt
    
    tk.Label(new_box, text="Prompt ใบหน้า:", anchor="w", bg="#FAFAF7", fg="#333", font=("Leelawadee UI", 9, "bold")).pack(fill="x", pady=(8, 2))
    new_prompt_text = tk.Text(new_box, height=2, wrap="word", bg="#FFFFFF", fg="#111", relief="flat", highlightthickness=1, highlightbackground="#D1D5DB")
    new_prompt_text.pack(fill="x")
    new_prompt_text.insert("1.0", story_face_prompt)
    g["story_face_prompt_text"] = new_prompt_text

    # Batch input lives in a separate dialog opened from one compact button.
    # Keep only its data/state here so the main Story Face page stays simple.
    batch_save_path = BASE / "story_face_batch_latest.json"
    try:
        saved_batch_payload = json.loads(batch_save_path.read_text(encoding="utf-8"))
        if not isinstance(saved_batch_payload, dict):
            saved_batch_payload = {}
    except Exception:
        saved_batch_payload = {}
    batch_source_state = {"text": str(saved_batch_payload.get("text") or "")}
    batch_status_var = tk.StringVar(
        value="โหลดข้อมูลชุดล่าสุดแล้ว" if batch_source_state["text"] else "ยังไม่มีข้อมูลชุด"
    )
    g["story_face_batch_source"] = batch_source_state
    g["story_face_batch_status_var"] = batch_status_var

    story_face_lock_bar = _builder_make_selection_lock_bar(new_box, lock_g, bg="#FAFAF7")
    story_face_lock_bar.pack(fill="x", pady=(8, 0))
    g["story_face_lock_bar"] = story_face_lock_bar
    
    new_log = _builder_make_log_box(new_box)
    new_log.pack(fill="x", pady=(8, 0))
    g["new_log_box"] = new_log
    
    def _new_log(msg):
        _builder_append_log(new_log, msg)
    
    g["_new_log"] = _new_log
    
    def _apply_story_face_character(character, selector=None):
        name = str(character.get("name", "")).strip()
        prompt = _build_story_face_prompt_from_character(character)
        new_name_var.set(name)
        new_prompt_text.delete("1.0", tk.END)
        new_prompt_text.insert("1.0", prompt)
        _new_log(_builder_set_selection_lock(lock_g, "character", name))
        if selector is not None:
            selector.destroy()
    
    def _open_story_face_selector():
        import re as _re
        context = _load_ref_context()
        context_chars = _extract_story_face_characters(context)
        batch_chars = []
        raw_lines = []
        try:
            saved = str(batch_source_state.get("text") or "").strip()
            if saved:
                raw_lines = saved.split("\n")
                parsed = _parse_batch_characters_via_bridge(saved)
                if isinstance(parsed, list):
                    batch_chars = parsed
        except Exception:
            pass
        # Mark important chars (** notation)
        imp_names = set()
        for _l in raw_lines:
            _sl = _l.strip()
            if "**" in _sl:
                _rest = _sl.split("**", 1)[1].strip()
                _rest = _rest.split("//")[0].strip()
                # First word is the name
                _n2 = _rest.split()[0].strip(",.;") if _rest else ""
                if _n2: imp_names.add(_n2)
        for _c in batch_chars:
            _cn = str(_c.get("name","") or _c.get("display_name","")).strip()
            if _cn in imp_names: _c["_important"] = True
        # Context: strip ** from names
        for _c in context_chars:
            _n = str(_c.get("name","")).strip()
            if "**" in _n:
                _c["_important"] = True
                _c["name"] = _c["name"].replace("**","").strip()
        if not context_chars and not batch_chars: _new_log("[Select] no chars"); return
        win = tk.Toplevel(root)
        win.title("Select character")
        win.configure(bg="#FFFFFF")
        win.geometry("580x520")
        win.transient(root)
        tab_bar = tk.Frame(win, bg="#FFFFFF")
        tab_bar.pack(fill="x", padx=14, pady=(14, 0))
        ctx_tab = tk.Button(tab_bar, text="From Context", bg="#2563EB", fg="white", relief="flat", bd=0, activebackground="#1D4ED8", padx=16, pady=8, font=("Leelawadee UI", 9, "bold"), cursor="hand2", command=lambda: None)
        ctx_tab.pack(side="left", padx=(0, 4))
        ds_tab = tk.Button(tab_bar, text="From Dataset", bg="#E5E7EB", fg="#111827", relief="flat", bd=0, activebackground="#D1D5DB", padx=16, pady=8, font=("Leelawadee UI", 9, "bold"), cursor="hand2", command=lambda: None)
        ds_tab.pack(side="left")
        cf = tk.Frame(win, bg="#FFFFFF")
        cf.pack(fill="both", expand=True, padx=14, pady=(10, 14))
        def _show_tab(tab):
            for w in cf.winfo_children(): w.destroy()
            if tab == "context":
                ctx_tab.config(bg="#2563EB",fg="white")
                ds_tab.config(bg="#E5E7EB",fg="#111827")
                chars = sorted(context_chars, key=lambda x: (0 if x.get("_important") else 1, str(x.get("name",""))))
            else:
                ctx_tab.config(bg="#E5E7EB",fg="#111827")
                ds_tab.config(bg="#2563EB",fg="white")
                chars = batch_chars
            if not chars: tk.Label(cf, text="Empty", bg="#FFFFFF",fg="#9CA3AF").pack(pady=40); return
            wrap = tk.Frame(cf, bg="#FFFFFF")
            wrap.pack(fill="both", expand=True)
            ca = tk.Canvas(wrap, bg="#FFFFFF", highlightthickness=0)
            sc = tk.Scrollbar(wrap, orient="vertical", command=ca.yview)
            inner = tk.Frame(ca, bg="#FFFFFF")
            inner.bind("<Configure>", lambda _e: ca.configure(scrollregion=ca.bbox("all")))
            ca.create_window((0, 0), window=inner, anchor="nw")
            ca.configure(yscrollcommand=sc.set)
            ca.pack(side="left", fill="both", expand=True)
            sc.pack(side="right", fill="y")
            for ch in chars:
                imp = ch.get("_important", False)
                n = str(ch.get("name","") or ch.get("display_name","") or "").strip()
                if tab == "context":
                    summ = " ".join(ch.get(k,"") for k in ("age","skin","hair") if ch.get(k))
                else:
                    age = str(ch.get("age","") or "").strip()
                    role = str(ch.get("role","") or "").strip()
                    summ = " | ".join(x for x in (age, role) if x)
                lbl = n + ("  " + summ if summ else "")
                bg2 = "#FEF2F2" if imp else "#F9FAFB"
                fg2 = "#991B1B" if imp else "#111827"
                pre = "* " if imp else ""
                tk.Button(inner, text=pre+lbl, anchor="w",
                    command=lambda c=ch: (_apply_story_face_character(c, win), win.destroy()),
                    bg=bg2, fg=fg2, activebackground="#E0E7FF",
                    activeforeground=fg2, relief="flat", bd=0,
                    padx=12, pady=9, wraplength=500, justify="left",
                    font=("Leelawadee UI", 9), cursor="hand2").pack(fill="x", padx=4, pady=2)
        ctx_tab.config(command=lambda: _show_tab("context"))
        ds_tab.config(command=lambda: _show_tab("dataset"))
        _show_tab("context")
        try: win.grab_set()
        except Exception: pass
    new_select_btn.config(command=_open_story_face_selector)
    g["_open_story_face_selector"] = _open_story_face_selector
    g["_apply_story_face_character"] = _apply_story_face_character
    
    new_gallery = tk.LabelFrame(new_page, text="แกลเลอรี", bg="#FAFAF7", fg="#1A1A1A", padx=8, pady=6)
    new_gallery.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    new_gallery_canvas = tk.Canvas(new_gallery, bg="#FAFAF7", highlightthickness=0)
    new_gallery_scroll = tk.Scrollbar(new_gallery, orient="vertical", command=new_gallery_canvas.yview)
    new_gallery_canvas.configure(yscrollcommand=new_gallery_scroll.set)
    new_gallery_inner = tk.Frame(new_gallery_canvas, bg="#FAFAF7")
    _sg_window = new_gallery_canvas.create_window((0, 0), window=new_gallery_inner, anchor="nw")
    new_gallery_canvas.pack(side="left", fill="both", expand=True)
    new_gallery_scroll.pack(side="right", fill="y")
    g["new_gallery_inner"] = new_gallery_inner
    new_gallery_images = []
    g["new_gallery_images"] = new_gallery_images
    story_face_running = [False]
    new_gallery_columns = 5
    for column_index in range(new_gallery_columns):
        new_gallery_inner.grid_columnconfigure(column_index, weight=1, uniform="story_face_gallery")

    def _sg_sync(_e=None):
        new_gallery_canvas.configure(scrollregion=new_gallery_canvas.bbox("all") or (0, 0, 0, 0))
        try:
            new_gallery_canvas.itemconfigure(_sg_window, width=max(new_gallery_canvas.winfo_width() - 4, 1))
        except Exception:
            pass

    def _sg_on_mousewheel(event):
        try:
            if not new_gallery_canvas.winfo_exists():
                return
            first, last = new_gallery_canvas.yview()
            if float(last) - float(first) >= 0.999:
                return
            delta = int(getattr(event, "delta", 0) or 0)
            if delta == 0:
                return
            new_gallery_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
            return "break"
        except Exception:
            return

    def _sg_bind_wheel(widget):
        try:
            widget.bind("<Enter>", lambda _e: new_gallery_canvas.bind_all("<MouseWheel>", _sg_on_mousewheel), add="+")
            widget.bind("<Leave>", lambda _e: new_gallery_canvas.unbind_all("<MouseWheel>"), add="+")
            widget.bind("<MouseWheel>", _sg_on_mousewheel, add="+")
        except Exception:
            pass

    new_gallery_inner.bind("<Configure>", _sg_sync)
    new_gallery_canvas.bind("<Configure>", _sg_sync)
    for _w in (new_gallery, new_gallery_canvas, new_gallery_inner, new_gallery_scroll):
        _sg_bind_wheel(_w)
    
    def _new_gallery_add(path, prepend=True):
        card_index = len(new_gallery_inner.winfo_children())
        row, column = divmod(card_index, new_gallery_columns)
        card = tk.Frame(new_gallery_inner, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5E7EB")
        thumb_box = tk.Frame(card, bg="#FFFFFF", width=140, height=170)
        thumb_box.pack(fill="both", expand=True, padx=6, pady=(6, 2))
        thumb_box.pack_propagate(False)
        try:
            from PIL import Image, ImageTk
            image = Image.open(path)
            image.thumbnail((130, 160), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            new_gallery_images.append(photo)
            tk.Label(thumb_box, image=photo, bg="#FFFFFF").pack(expand=True)
        except Exception:
            tk.Label(thumb_box, text="ไม่มี preview", bg="#FFFFFF", fg="#9CA3AF", wraplength=150).pack(expand=True)
        tk.Label(card, text=os.path.basename(path), bg="#FFFFFF", fg="#111", anchor="center", wraplength=180).pack(fill="x", padx=6, pady=(2, 3))
        tk.Button(card, text="📂 เปิด", command=lambda p=path: subprocess.Popen(["explorer", "/select,", p])).pack(pady=(0, 6))
        card.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
    g["_new_gallery_add"] = _new_gallery_add
    
    def _set_story_face_running(running):
        story_face_running[0] = bool(running)
        try:
            new_make_btn.config(state=(tk.DISABLED if running else tk.NORMAL), text=("กำลังสร้าง Face..." if running else "🎭 สร้าง Face"))
            new_select_btn.config(state=(tk.DISABLED if running else tk.NORMAL))
        except Exception:
            pass
    
    def generate_story_face():
        name = new_name_var.get().strip()
        prompt = new_prompt_text.get("1.0", tk.END).strip()
        if not name:
            _new_log("[สร้าง Face] ใส่ชื่อหรือกด Select ก่อน")
            return
        if not prompt:
            _new_log("[สร้าง Face] ไม่มี Prompt ใบหน้า")
            return
        if story_face_running[0]:
            _new_log("[สร้าง Face] กำลังสร้างอยู่ — รอให้งานเดิมเสร็จก่อน")
            return
        _new_log(_builder_set_selection_lock(lock_g, "character", name))
        # Inject age from dropdown (วัย). "อัตโนมัติ" keeps story/character age instead of a fixed number.
        age_label = str(new_age_var.get() or "อัตโนมัติ").strip()
        age_val = _FACE_AGE_MAP.get(age_label, "35")
        if age_label == "อัตโนมัติ" or age_val == "auto":
            prompt = (
                prompt
                .replace(", {age} years old", ", age matching the character story identity automatically")
                .replace("{age} years old", "age matching the character story identity automatically")
                .replace("{age}", "auto from character identity")
            )
        else:
            prompt = prompt.replace("{age}", age_val)
        prompt = prompt.replace("{name}", name)
        _set_story_face_running(True)
        _new_log(f"[สร้าง Face] เริ่มสร้างรูป: {name} (วัย: {age_label})")
    
        def worker():
            try:
                payload = _build_story_face_payload(prompt)
                story_face_dir = export_story_face_dir
                story_face_dir.mkdir(parents=True, exist_ok=True)
                lock = globals().get("_bridge_queue_lock")
                def request_image():
                    if "_wait_bridge_free" in globals():
                        globals()["_wait_bridge_free"](log_fn=_new_log)
                    refine = g.get("_refine_prompt_via_ai") or globals().get("_refine_prompt_via_ai")
                    if callable(refine):
                        _new_log(f"[refine] ส่ง GPT แปลง prompt Face: {name}")
                    # Select already embeds only that character's details in
                    # `prompt`; manual input contains only what the user typed.
                    # Do not append the whole story context in either case.
                    final_prompt = refine(prompt, kind="face", use_context=False) if callable(refine) else prompt
                    if final_prompt != prompt:
                        _new_log(f"[refine] ใช้ prompt ใหม่ ({len(final_prompt)} chars)")
                    payload = _build_story_face_payload(final_prompt)
                    return g["_do_image_request"](payload, is_edit=False, prompt=final_prompt, name_hint=f"{name}-face", raw_prompt=prompt, output_dir=str(story_face_dir), save_sidecar=False)
                if lock:
                    with lock:
                        out = request_image()
                else:
                    out = request_image()
    
                def on_success():
                    try:
                        _new_gallery_add(out, True)
                        _new_log(f"✓ สร้าง Face สำเร็จ: {out}")
                        _notify_done()
                    except Exception as gallery_error:
                        _new_log(f"ERROR gallery: {gallery_error}")
                    _set_story_face_running(False)
                root.after(0, on_success)
            except Exception as error:
                def on_error(error=error):
                    _new_log(f"ERROR: {error}")
                    _set_story_face_running(False)
                root.after(0, on_error)
        threading.Thread(target=worker, daemon=True).start()
    g["generate_story_face"] = generate_story_face
    
    def _new_action_waiting(label):
        _new_log(f"[{label}] รอกำหนดการทำงานของปุ่ม")
    
    # ── Auto Face: generate faces for all characters from Prompt Context ──
    auto_face_running = [False]
    auto_face_stop = [False]
    saved_characters = saved_batch_payload.get("characters")
    if not isinstance(saved_characters, list):
        saved_characters = []
    saved_source = str(saved_batch_payload.get("source") or "")
    if saved_source != batch_source_state["text"]:
        saved_source = ""
        saved_characters = []
    batch_cache = {
        "source": saved_source,
        "characters": saved_characters,
        "design_page": str(saved_batch_payload.get("design_page") or ""),
    }

    def _persist_batch_state():
        """Keep the latest batch text and analyzed cast across app restarts."""
        payload = {
            "text": str(batch_source_state.get("text") or ""),
            "source": str(batch_cache.get("source") or ""),
            "characters": list(batch_cache.get("characters") or []),
            "design_page": str(batch_cache.get("design_page") or ""),
        }
        batch_save_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = batch_save_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(batch_save_path)

    def _clean_json_response(text):
        text = str(text or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = text.replace("```", "").strip()
        try:
            return json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
            raise

    def _fallback_batch_characters(text):
        """Conservative fallback: one numbered row becomes one face job."""
        rows = re.findall(
            r"(?m)^\s*\d+(?:\.\d+)*[.)]?\s*(.+?)\s*$",
            str(text or ""),
        )
        out = []
        for row in rows:
            clean = re.sub(r"\*+", "", row).strip()
            lowered = clean.casefold()
            non_person_markers = (
                "รูปถ่าย", "prop", "พร็อพ", "พ็อป", "สิ่งของ", "สถานที่",
                "อาคาร", "ห้องนอน", "ห้องน้ำ", "รถยนต์", "รถจักรยานยนต์",
                "สัตว์", "สุนัข", "แมว", "เอกสาร",
            )
            if not clean or any(marker in lowered for marker in non_person_markers):
                continue
            name = re.split(
                r"\s*(?:\(|วัย|ตอนวัย|พ่อของ|แม่ของ|อาผู้ชาย|ของดวงเดือน|ชุด)",
                clean,
                maxsplit=1,
            )[0].strip(" :-–—")
            if not name:
                name = clean[:50].strip()
            out.append({
                "name": name,
                "variant": "",
                "age": "",
                "role": clean,
                "appearance": "",
                "clothes": "",
                "source": clean,
            })
        return out

    def _parse_batch_characters_via_bridge(text):
        """Turn free-form numbered data into one face job per identity/age."""
        source = str(text or "").strip()
        if not source:
            return []
        if batch_cache["source"] == source and batch_cache["characters"]:
            return list(batch_cache["characters"])

        system = (
            "คุณเป็นตัวแยกรายการตัวละครสำหรับสร้างภาพใบหน้า ไม่ได้สร้างภาพ "
            "ก่อนแยกรายคน ให้เขียน Character Bible รวมหนึ่งหน้าโดยมองนักแสดงทุกคนพร้อมกัน "
            "และออกแบบให้แต่ละคนแตกต่างกันชัดเจนด้านรูปหน้า สัดส่วนตา คิ้ว จมูก ปาก กราม "
            "โหนกแก้ม สีผิว พื้นผิวผิว รอยตำหนิ และอายุ ห้ามใช้ใบหน้าต้นแบบซ้ำกัน. "
            "ตอบ JSON เท่านั้นในรูป {\"design_page\":\"...\",\"subjects\":[...]}. "
            "design_page ต้องเป็นแผนรวมทั้งเรื่องที่อธิบายความแตกต่างของทุกใบหน้าในหน้าเดียว. "
            "แต่ละ subject ต้องมี name, variant, age, role, appearance, face_design, skin_detail, hair, clothes, source. "
            "รับเฉพาะมนุษย์ที่ควรมีภาพใบหน้าตัวละครหนึ่งคนต่อหนึ่ง subject เท่านั้น. "
            "ตัด Prop, สิ่งของ, ยานพาหนะ, สถานที่, อาคาร, ห้อง, สัตว์, เอกสาร, "
            "รูปถ่ายกลุ่ม และรายการที่ไม่ใช่บุคคลออกทั้งหมด. "
            "แยกคนละ identity เป็นคนละ subject. ตัวละครชื่อเดิมที่ต่างช่วงวัยให้แยกเป็นคนละ subject "
            "และใส่ variant เช่น วัยเด็ก/วัยรุ่น/วัยหนุ่ม/วัยกลางคน. "
            "ถ้ามีเครื่องหมาย + ที่หมายถึงคนละคน เช่น ลูกชาย + ลูกสะใภ้ หรือ วิชัย + ภรรยา "
            "ให้แยกคนละ subject. ถ้า + เป็นเพียงหลายชุดของคนเดิม ไม่ต้องสร้าง identity ใหม่ "
            "แต่รวมชุดไว้ใน clothes. ข้ามรายการที่เป็นรูปถ่ายกลุ่มหรือวัตถุและไม่ได้เพิ่มคนใหม่. "
            "ห้ามแต่งชื่อจริงให้คนที่บทไม่ได้ให้ชื่อ ให้ใช้ชื่อบทบาท เช่น ภรรยาของวิชัย. "
            "รักษาชื่อไทยและข้อมูลยุค/เรื่องจากหัวข้อไว้ใน role/source. ห้ามอธิบายนอก JSON."
        )
        user = (
            "แยกข้อมูลชุดนี้เป็นงานสร้างใบหน้าทั้งหมด:\n\n"
            + source[:12000]
        )
        base_fn = globals().get("_chatgpt_api_base")
        base = base_fn() if callable(base_fn) else "http://127.0.0.1:8000/v1"
        payload = json.dumps({
            "model": "gpt-5-5",
            "chatgpt_image_intercept": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
        }, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=payload,
            headers={
                "Authorization": "Bearer local-dev-key",
                "Content-Type": "application/json",
                "User-Agent": "Tidmun-Studio/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = (
                (((result.get("choices") or [{}])[0].get("message") or {}).get("content"))
                or ""
            )
            parsed = _clean_json_response(content)
            raw_subjects = parsed.get("subjects") if isinstance(parsed, dict) else None
            if not isinstance(raw_subjects, list):
                raise RuntimeError("GPT ไม่คืน subjects")
            subjects = []
            seen = set()
            for item in raw_subjects:
                if not isinstance(item, dict):
                    continue
                normalized = {
                    key: str(item.get(key) or "").strip()
                    for key in (
                        "name", "variant", "age", "role",
                        "appearance", "face_design", "skin_detail",
                        "hair", "clothes", "source",
                    )
                }
                if not normalized["name"]:
                    continue
                key = (
                    normalized["name"].casefold(),
                    normalized["variant"].casefold(),
                    normalized["age"].casefold(),
                )
                if key in seen:
                    continue
                seen.add(key)
                subjects.append(normalized)
            if not subjects:
                raise RuntimeError("ไม่พบรายชื่อตัวละครจากข้อมูลชุด")
            design_page = str(parsed.get("design_page") or "").strip()
            if not design_page:
                design_page = "Character Bible รวม: " + "; ".join(
                    f"{item['name']} {item.get('variant', '')}: {item.get('face_design') or item.get('appearance') or item.get('role')}"
                    for item in subjects
                )
        except Exception as error:
            _new_log(f"[ข้อมูลชุด] GPT แยกไม่สำเร็จ ใช้รายการเลขแทน: {error}")
            subjects = _fallback_batch_characters(source)
            design_page = (
                "Character Bible รวมจากรายการต้นฉบับ: ตัวละครแต่ละคนต้องมีโครงหน้า "
                "ตา คิ้ว จมูก ปาก กราม สีผิว พื้นผิว และริ้วรอยแตกต่างกันชัดเจน. "
                + source[:1600]
            )
        batch_cache["source"] = source
        batch_cache["characters"] = list(subjects)
        batch_cache["design_page"] = design_page
        return subjects

    def _batch_face_prompt(character, overview):
        name = str(character.get("name") or "").strip()
        variant = str(character.get("variant") or "").strip()
        age = str(character.get("age") or "").strip()
        role = str(character.get("role") or "").strip()
        appearance = str(character.get("appearance") or "").strip()
        face_design = str(character.get("face_design") or "").strip()
        skin_detail = str(character.get("skin_detail") or "").strip()
        hair = str(character.get("hair") or "").strip()
        clothes = str(character.get("clothes") or "").strip()
        identity = name + (f" ({variant})" if variant else "")
        details = "; ".join(
            value for value in (
                f"age: {age}" if age else "",
                f"role: {role}" if role else "",
                f"appearance: {appearance}" if appearance else "",
                f"face design: {face_design}" if face_design else "",
                f"skin detail: {skin_detail}" if skin_detail else "",
                f"hair identity: {hair}" if hair else "",
                f"clothes: {clothes}" if clothes else "",
            ) if value
        )
        rules = (
            "สร้างเพียงคนเป้าหมายหนึ่งคน ใบหน้าต้องต่างจากตัวละครอื่นชัดเจนทั้งรูปหน้า ตา คิ้ว จมูก ปาก "
            "กราม โหนกแก้ม สีผิวและตำหนิ ห้ามใช้หน้าแม่แบบซ้ำ. close-up head-and-shoulders, full front-facing, "
            "centered, looking straight at camera, neutral expression. Mouth fully closed with relaxed closed lips; "
            "absolutely no visible teeth, no open mouth, no smile. Forehead, cheeks, hairline and both ears visible. "
            "Hair fully pulled and secured behind head; no bangs or loose strands over forehead, temples, eyebrows, "
            "cheeks, jawline or ears. Age-accurate unretouched skin microdetail: visible pores, fine lines, wrinkles, "
            "crow's-feet, nasolabial folds, spots, freckles, moles, scars and uneven texture where appropriate. "
            "Older faces show pronounced authentic age lines. No beauty filter, airbrushing, waxy, porcelain, plastic "
            "or excessively smooth skin. Photorealistic Thai identity, color-accurate natural skin, neutral light-gray "
            "background. Shadowless calibrated white studio light at D55: identical large softboxes symmetrically left "
            "and right with equal power plus centered fill; both sides of face equal brightness and color, uniform "
            "exposure forehead to neck. No yellow, orange, warm, sepia, green or blue cast; no side, rim, back, dramatic "
            "or cinematic light, no dark half of face, no collage, grid or extra person. Tack-sharp 85mm micro-focus with high local contrast, crisp pores and skin texture, no soft blur, no diffusion filter, no plastic smoothing, 3:4 portrait."
        )
        head = (
            f"สร้างรูปภาพใบหน้าตัวละครไทยหนึ่งคนเท่านั้น TARGET CHARACTER: {identity}. "
            f"TARGET DETAILS: {details}. "
            f"CAST CHARACTER BIBLE ใช้เปรียบเทียบเอกลักษณ์เท่านั้น ห้ามวาดคนอื่น: {overview}. "
        )
        max_chars = 2000
        head_room = max(120, max_chars - len(rules) - 2)
        return head[:head_room].rstrip(" ,;.") + ". " + rules
    
    def _extract_auto_face_characters(text):
        """Extract full character objects from prompt_ref_context JSON."""
        try:
            import json as _j
            ctx = _j.loads(text)
            chars = ctx.get("characters", []) if isinstance(ctx, dict) else []
            out = []
            seen = set()
            for c in chars:
                if not isinstance(c, dict):
                    continue
                name = str(c.get("name", "")).strip()
                if name and name not in seen:
                    seen.add(name)
                    out.append(c)
            return out
        except Exception:
            return []
    
    def _set_auto_face_button_running(running):
        btn = new_auto_btn
        try:
            if running:
                btn.config(text="⏹ หยุด", command=stop_auto_face, state=tk.NORMAL, bg="#DC2626", activebackground="#B91C1C")
            else:
                btn.config(text="📋 ข้อมูลชุด", command=_open_story_face_batch_dialog, state=tk.NORMAL, bg="#0EA5E9", activebackground="#0284C7")
        except Exception:
            pass
    
    def stop_auto_face():
        auto_face_stop[0] = True
        _new_log("[auto-face] ขอหยุด — จะหยุดหลักรูปที่กำลังสร้างเสร็จ")
    
    def generate_auto_face():
        if auto_face_running[0]:
            _new_log("[auto-face] กำลังทำงานอยู่ — รอเสร็จก่อน")
            return
        batch_source = str(batch_source_state.get("text") or "").strip()
        auto_face_stop[0] = False
        auto_face_running[0] = True
        root.after(0, lambda: _set_auto_face_button_running(True))
        if batch_source:
            batch_status_var.set("กำลังแยกรายชื่อด้วย GPT...")
            _new_log("[ข้อมูลชุด] กำลังแยกชื่อ ช่วงวัย บทบาท และชุด...")
        else:
            _new_log("[auto-face] ไม่พบข้อมูลชุด — ใช้รายชื่อจาก Prompt Context")

        def worker():
            try:
                lock = globals().get("_bridge_queue_lock")
                story_face_dir = export_story_face_dir
                story_face_dir.mkdir(parents=True, exist_ok=True)

                def resolve_characters():
                    if batch_source:
                        characters = _parse_batch_characters_via_bridge(batch_source)
                        overview = str(batch_cache.get("design_page") or "").strip()
                        if not overview:
                            overview = re.sub(
                                r"(?m)^\s*\d+(?:\.\d+)*[.)]?\s*.+$",
                                "",
                                batch_source,
                            ).strip() or batch_source[:1600]
                        return characters, overview, "ข้อมูลชุด"
                    try:
                        context_text = _load_ref_context()
                    except Exception:
                        context_text = ""
                    return _extract_auto_face_characters(context_text), "", "Prompt Context"

                def run_one(idx, character, characters, overview, source_kind):
                    name = str(character.get("name", "")).strip()
                    if auto_face_stop[0]:
                        _new_log(f"[auto-face] หยุดแล้ว — ข้าม {name}")
                        return
                    variant = str(character.get("variant", "")).strip()
                    display_name = name + (f" — {variant}" if variant else "")
                    _new_log(f"[auto-face] {idx}/{len(characters)} — เริ่มสร้าง: {display_name}")
                    if source_kind == "ข้อมูลชุด":
                        prompt = _batch_face_prompt(character, overview)
                    else:
                        # Build prompt from full Prompt Context details, same as Select.
                        builder = globals().get("_build_story_face_prompt_from_character")
                        if callable(builder):
                            prompt = builder(character)
                        else:
                            tmpl = g.get("story_face_prompt_template", "")
                            prompt = tmpl.replace("{name}", name)
                    age_val = _FACE_AGE_MAP.get(new_age_var.get(), "35")
                    prompt = prompt.replace("{age}", age_val).replace("{name}", name)
                    payload = _build_story_face_payload(prompt)
                    if "_wait_bridge_free" in globals():
                        globals()["_wait_bridge_free"](log_fn=_new_log)
                    refine = g.get("_refine_prompt_via_ai") or globals().get("_refine_prompt_via_ai")
                    if callable(refine):
                        _new_log(f"[refine] ส่ง GPT แปลง prompt Face: {name}")
                    # This prompt already contains only the selected character
                    # object; do not append the entire story context.
                    final_prompt = refine(prompt, kind="face", use_context=False) if callable(refine) else prompt
                    if final_prompt != prompt:
                        _new_log(f"[refine] {name}: prompt ใหม่ ({len(final_prompt)} chars)")
                    payload = _build_story_face_payload(final_prompt)
                    hint = f"{name}-{variant}-face" if variant else f"{name}-face"
                    try:
                        out = g["_do_image_request"](
                            payload, is_edit=False, prompt=final_prompt,
                            name_hint=hint, raw_prompt=prompt,
                            output_dir=str(story_face_dir), save_sidecar=False,
                        )
                    except Exception as exc:
                        raise RuntimeError(
                            f"ขั้นสร้างรูปผ่าน GPT ล้มเหลว: {exc}"
                        ) from exc
                    root.after(0, lambda out=out, display_name=display_name: (_new_log(f"✓ {display_name}: {out}"), _new_gallery_add(out, True), _notify_done()))

                def run_all():
                    characters, overview, source_kind = resolve_characters()
                    if not characters:
                        if batch_source:
                            raise RuntimeError("ไม่พบรายชื่อในข้อมูลชุด กรุณาใช้รายการขึ้นต้น 1., 2., 2.1 ...")
                        raise RuntimeError("ไม่พบตัวละครใน Prompt Context — วางข้อมูลชุดหรือสรุปบทหลักก่อน")
                    names = [
                        str(c.get("name", "")).strip()
                        + (f" ({str(c.get('variant', '')).strip()})" if str(c.get("variant", "")).strip() else "")
                        for c in characters
                    ]
                    root.after(
                        0,
                        lambda names=names, source_kind=source_kind: (
                            batch_status_var.set(f"พบ {len(names)} งานจาก {source_kind}"),
                            _new_log(f"[auto-face] จะสร้างทีละใบหน้า {len(names)} งาน: {', '.join(names)}"),
                        ),
                    )
                    for idx, character in enumerate(characters, 1):
                        if auto_face_stop[0]:
                            _new_log("[auto-face] หยุดตามคำสั่ง")
                            break
                        run_one(idx, character, characters, overview, source_kind)
                if lock:
                    with lock: run_all()
                else:
                    run_all()
            except Exception as e:
                root.after(0, lambda e=e: _new_log(f"[auto-face] ERROR: {e}"))
            finally:
                auto_face_running[0] = False
                root.after(0, lambda: _set_auto_face_button_running(False))
        threading.Thread(target=worker, daemon=True).start()
    g["generate_auto_face"] = generate_auto_face
    g["stop_auto_face"] = stop_auto_face

    def _open_story_face_batch_dialog():
        if auto_face_running[0]:
            _new_log("[ข้อมูลชุด] กำลังสร้างอยู่ — กดหยุดหรือรอให้เสร็จก่อน")
            return
        win = tk.Toplevel(root)
        win.title("ข้อมูลตัวละครเป็นชุด — นิทาน")
        dialog_width, dialog_height = 780, 620
        try:
            root.update_idletasks()
            x = root.winfo_rootx() + max(0, (root.winfo_width() - dialog_width) // 2)
            y = root.winfo_rooty() + max(0, (root.winfo_height() - dialog_height) // 2)
            win.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        except Exception:
            win.geometry(f"{dialog_width}x{dialog_height}")
        win.minsize(700, 540)
        win.configure(bg="#FFFFFF")
        win.transient(root)

        header = tk.Frame(win, bg="#FFFFFF")
        header.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(
            header,
            text="ข้อมูลตัวละครเป็นชุด",
            bg="#FFFFFF",
            fg="#111827",
            font=("Leelawadee UI", 14, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            header,
            text="วางข้อมูลแบบรายการ 1., 2., 2.1 ... ระบบจะแยกคน ช่วงวัย บทบาท และชุด ก่อนสร้างใบหน้าทีละรูป",
            bg="#FFFFFF",
            fg="#6B7280",
            font=("Leelawadee UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        input_frame = tk.LabelFrame(
            win,
            text="1. วางข้อมูล",
            bg="#FFFFFF",
            fg="#111827",
            padx=8,
            pady=6,
        )
        input_frame.pack(fill="x", padx=16, pady=(0, 8))
        editor = tk.Text(
            input_frame,
            height=12,
            wrap="word",
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            relief="solid",
            bd=1,
            padx=10,
            pady=8,
            font=("Leelawadee UI", 10),
        )
        editor.pack(fill="x")
        editor.insert("1.0", str(batch_source_state.get("text") or ""))

        preview_frame = tk.LabelFrame(
            win,
            text="2. รายการใบหน้าที่ระบบจะสร้าง",
            bg="#FFFFFF",
            fg="#111827",
            padx=8,
            pady=6,
        )
        preview = tk.Text(
            preview_frame,
            height=9,
            wrap="word",
            bg="#F9FAFB",
            fg="#111827",
            relief="flat",
            padx=8,
            pady=6,
            font=("Leelawadee UI", 9),
            state=tk.DISABLED,
        )
        preview.pack(fill="both", expand=True)

        controls = tk.Frame(win, bg="#FFFFFF")
        controls.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
        dialog_status = tk.StringVar(value=batch_status_var.get())
        tk.Label(
            controls,
            textvariable=dialog_status,
            bg="#FFFFFF",
            fg="#6B7280",
            anchor="w",
            font=("Leelawadee UI", 9),
        ).pack(side="left", fill="x", expand=True)

        def save_text():
            value = editor.get("1.0", tk.END).strip()
            changed = value != str(batch_source_state.get("text") or "")
            batch_source_state["text"] = value
            if changed:
                batch_cache.update(source="", characters=[], design_page="")
            _persist_batch_state()
            message = "บันทึกข้อมูลล่าสุดแล้ว" if value else "บันทึกข้อมูลว่างแล้ว"
            batch_status_var.set(message)
            dialog_status.set(message)
            return value

        def render_preview(subjects):
            preview.config(state=tk.NORMAL)
            preview.delete("1.0", tk.END)
            if not subjects:
                preview.insert(
                    "1.0",
                    "ไม่พบรายการที่เป็นบุคคล จึงยังไม่มีรูปใบหน้าที่จะสร้าง\n"
                    "Prop, สิ่งของ, สถานที่, สัตว์ และรูปถ่ายกลุ่มจะถูกตัดออก",
                )
                create_btn.config(state=tk.DISABLED)
            else:
                design_page = str(batch_cache.get("design_page") or "").strip()
                if design_page:
                    preview.insert(
                        tk.END,
                        "CHARACTER BIBLE — แผนใบหน้ารวมทั้งเรื่อง\n"
                        + design_page
                        + "\n\n"
                        + ("─" * 72)
                        + "\n\n",
                    )
                preview.insert(
                    tk.END,
                    f"จะสร้างทั้งหมด {len(subjects)} รูป — เฉพาะบุคคลด้านล่าง\n\n",
                )
                for index, subject in enumerate(subjects, 1):
                    name = str(subject.get("name") or "").strip()
                    variant = str(subject.get("variant") or "").strip()
                    age = str(subject.get("age") or "").strip()
                    role = str(subject.get("role") or "").strip()
                    face_design = str(subject.get("face_design") or "").strip()
                    skin_detail = str(subject.get("skin_detail") or "").strip()
                    hair = str(subject.get("hair") or "").strip()
                    clothes = str(subject.get("clothes") or "").strip()
                    title = name + (f" — {variant}" if variant else "")
                    detail = " | ".join(
                        value for value in (
                            f"วัย: {age}" if age else "",
                            f"บทบาท: {role}" if role else "",
                            f"ใบหน้า: {face_design}" if face_design else "",
                            f"ผิว: {skin_detail}" if skin_detail else "",
                            f"ผม: {hair}" if hair else "",
                            f"ชุด: {clothes}" if clothes else "",
                        ) if value
                    )
                    preview.insert(
                        tk.END,
                        f"{index}. {title}" + (f"\n   {detail}" if detail else "") + "\n",
                    )
                create_btn.config(state=tk.NORMAL)
            preview.config(state=tk.DISABLED)
            preview.see("1.0")

        def save_and_close():
            save_text()
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

        def clear_text():
            editor.delete("1.0", tk.END)
            batch_source_state["text"] = ""
            batch_cache.update(source="", characters=[], design_page="")
            batch_status_var.set("ยังไม่มีข้อมูลชุด")
            dialog_status.set("ล้างข้อมูลชุดแล้ว")
            _persist_batch_state()
            render_preview([])

        def analyze():
            value = save_text()
            if not value:
                dialog_status.set("กรุณาวางข้อมูลตัวละครก่อน")
                return
            analyze_btn.config(state=tk.DISABLED, text="กำลังวิเคราะห์...")
            create_btn.config(state=tk.DISABLED)
            dialog_status.set("กำลังวิเคราะห์ว่าอะไรเป็นบุคคลและควรสร้างใบหน้าอะไร...")

            def worker():
                try:
                    subjects = _parse_batch_characters_via_bridge(value)
                    error = None
                except Exception as exc:
                    subjects = []
                    error = str(exc)

                def done():
                    try:
                        current = editor.get("1.0", tk.END).strip()
                        analyze_btn.config(state=tk.NORMAL, text="🔎 วิเคราะห์")
                        if current != value:
                            create_btn.config(state=tk.DISABLED)
                            dialog_status.set("ข้อมูลถูกแก้ระหว่างวิเคราะห์ — กดวิเคราะห์ใหม่")
                            return
                        if error:
                            dialog_status.set("วิเคราะห์ไม่สำเร็จ: " + error)
                            render_preview([])
                            return
                        render_preview(subjects)
                        _persist_batch_state()
                        message = f"วิเคราะห์แล้ว: จะสร้าง {len(subjects)} รูป"
                        batch_status_var.set(message)
                        dialog_status.set(message + " — ตรวจรายการก่อนกดสร้างทั้งหมด")
                    except Exception:
                        pass
                root.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        def create_all():
            value = save_text()
            if not value:
                dialog_status.set("กรุณาวางข้อมูลตัวละครก่อน")
                return
            if batch_cache.get("source") != value or not batch_cache.get("characters"):
                create_btn.config(state=tk.DISABLED)
                dialog_status.set("กรุณากดวิเคราะห์และตรวจรายการก่อนสร้าง")
                return
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()
            generate_auto_face()

        def on_editor_modified(_event=None):
            try:
                if not editor.edit_modified():
                    return
                editor.edit_modified(False)
                current = editor.get("1.0", tk.END).strip()
                batch_source_state["text"] = current
                if batch_cache.get("source") != current:
                    batch_cache.update(source="", characters=[], design_page="")
                    create_btn.config(state=tk.DISABLED)
                    dialog_status.set("ข้อมูลเปลี่ยนแล้ว — กดวิเคราะห์เพื่อดูรายการใหม่")
            except Exception:
                pass

        tk.Button(
            controls,
            text="ปิด",
            command=save_and_close,
            bg="#F3F4F6",
            fg="#111827",
            relief="flat",
            padx=14,
            pady=7,
            font=("Leelawadee UI", 9, "bold"),
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            controls,
            text="💾 Save",
            command=save_text,
            bg="#16A34A",
            fg="#FFFFFF",
            relief="flat",
            padx=14,
            pady=7,
            font=("Leelawadee UI", 9, "bold"),
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            controls,
            text="ล้าง",
            command=clear_text,
            bg="#DC2626",
            fg="#FFFFFF",
            relief="flat",
            padx=14,
            pady=7,
            font=("Leelawadee UI", 9, "bold"),
        ).pack(side="right", padx=(6, 0))
        create_btn = tk.Button(
            controls,
            text="⚡ สร้างทั้งหมด",
            command=create_all,
            bg="#0EA5E9",
            fg="#FFFFFF",
            relief="flat",
            padx=16,
            pady=7,
            font=("Leelawadee UI", 9, "bold"),
            state=tk.DISABLED,
        )
        create_btn.pack(side="right", padx=(6, 0))
        analyze_btn = tk.Button(
            controls,
            text="🔎 วิเคราะห์",
            command=analyze,
            bg="#7C3AED",
            fg="#FFFFFF",
            relief="flat",
            padx=16,
            pady=7,
            font=("Leelawadee UI", 9, "bold"),
        )
        analyze_btn.pack(side="right", padx=(6, 0))

        # Pack the expandable preview only after the fixed footer.  This keeps
        # every action button visible even on shorter screens.
        preview_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        editor.edit_modified(False)
        editor.bind("<<Modified>>", on_editor_modified, add="+")
        saved_source = str(batch_source_state.get("text") or "").strip()
        if saved_source and batch_cache.get("source") == saved_source and batch_cache.get("characters"):
            render_preview(batch_cache["characters"])
            dialog_status.set(
                f"วิเคราะห์แล้ว: จะสร้าง {len(batch_cache['characters'])} รูป"
            )

        win.protocol("WM_DELETE_WINDOW", save_and_close)
        try:
            win.grab_set()
            editor.focus_set()
        except Exception:
            pass

    g["_open_story_face_batch_dialog"] = _open_story_face_batch_dialog
    
    new_make_btn = tk.Button(new_row, text="🎭 สร้าง Face", command=generate_story_face, bg="#6D28D9", fg="white", activebackground="#7C3AED", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold"))
    new_make_btn.pack(side="left", padx=4)
    
    # Pack Select AFTER สร้าง Face (so สร้าง Face appears first on the left)
    new_select_btn.pack(side="left", padx=(0, 4))
    new_auto_btn = tk.Button(new_row, text="📋 ข้อมูลชุด", command=_open_story_face_batch_dialog, bg="#0EA5E9", fg="white", activebackground="#0284C7", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold"))
    new_auto_btn.pack(side="left", padx=4)
    tk.Button(new_row, text="Clear", command=lambda: (new_name_var.set(""), new_log.delete("1.0", tk.END)), bg="#DC2626", fg="white", activebackground="#B91C1C", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=4)
    tk.Button(new_row, text="🧹 ล้างรูป", command=lambda: ([child.destroy() for child in new_gallery_inner.winfo_children()], new_gallery_images.clear(), _new_log("ล้าง Gallery แล้ว")), bg="#DC2626", fg="white", activebackground="#B91C1C", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, width=14, height=1, font=("Leelawadee UI", 9, "bold")).pack(side="left", padx=4)
    g["new_make_btn"] = new_make_btn
    g["new_auto_btn"] = new_auto_btn
    g["new_page"] = new_page
    return new_page
