# -*- coding: utf-8 -*-
"""SnapGen karaoke page.

This module owns the widgets, state, and callbacks for this page only.
"""
from __future__ import annotations

import tkinter as tk


def install(g: dict, root: tk.Misc) -> tk.Misc:
    """Build this page and return its root frame."""
    globals().update(g)
    # ── Karaoke Page (built via snapgen_page_builder) ─────────────────────
    from snapgen_page_builder import (
        build_page, make_action_row, make_styled_button,
        make_label, make_entry, make_status_label,
        make_log_box, append_log,
    )
    
    karaoke_page, karaoke_box = build_page(root, "🔤 คาราโอเกะ — แปลงชื่อไทยเป็นคำอ่าน")
    
    # Form rows — keep labels, entries, and buttons on the same grid so the
    # two lines line up cleanly instead of drifting by each row's packed width.
    karaoke_form = make_action_row(karaoke_box)
    karaoke_form.pack(fill="x", pady=(0, 12))
    karaoke_form.grid_columnconfigure(0, minsize=92)
    karaoke_form.grid_columnconfigure(1, minsize=360)
    karaoke_form.grid_columnconfigure(2, minsize=170)
    karaoke_form.grid_columnconfigure(3, minsize=170)

    make_label(karaoke_form, "ชื่อภาษาไทย:", sub=True).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 10))
    karaoke_name_var = tk.StringVar()
    karaoke_input = make_entry(karaoke_form, karaoke_name_var, width=36)
    karaoke_input.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(0, 10), ipady=3)

    # One paste only. Windows/Tk can fire Control-v then <<Paste>> for the same keypress.
    _karaoke_paste_guard = {"ts": 0.0}

    def _paste_karaoke_text(replace_all=False):
        """Paste clipboard into the Thai name field. Returns True on success."""
        paste_fn = g.get("_paste_into_widget")
        try:
            txt = str(root.clipboard_get())
        except Exception:
            return False
        txt = str(txt or "").strip()
        if not txt:
            return False
        if replace_all:
            karaoke_name_var.set(txt)
            try:
                karaoke_input.icursor(tk.END)
                karaoke_input.focus_set()
            except Exception:
                pass
            return True
        if callable(paste_fn):
            ok = paste_fn(karaoke_input, txt)
            return bool(ok)
        try:
            if karaoke_input.selection_present():
                karaoke_input.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except Exception:
            pass
        try:
            karaoke_input.insert(tk.INSERT, txt)
        except Exception:
            karaoke_name_var.set(txt)
        return True

    def _paste_karaoke_once(_event=None):
        import time as _time
        now = _time.time()
        if now - float(_karaoke_paste_guard.get("ts") or 0.0) < 0.12:
            return "break"
        _karaoke_paste_guard["ts"] = now
        _paste_karaoke_text(replace_all=False)
        return "break"

    for _seq in ("<Control-v>", "<Control-V>"):
        karaoke_input.bind(_seq, _paste_karaoke_once)
    
    make_label(karaoke_form, "คำอ่าน:", sub=True).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
    karaoke_result_var = tk.StringVar()
    karaoke_result_entry = make_entry(karaoke_form, karaoke_result_var, width=36, readonly=True)
    karaoke_result_entry.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 8), ipady=3)
    
    # Status
    karaoke_status_var = tk.StringVar()
    make_status_label(karaoke_box, karaoke_status_var).pack(anchor="w")
    karaoke_log_box = make_log_box(karaoke_box)
    karaoke_log_box.pack(fill="x", pady=(8, 0))
    
    def _karaoke_status(msg):
        karaoke_status_var.set(msg)
        append_log(karaoke_log_box, msg)

    def _notify_done():
        notify = g.get("_snapgen_notify_done")
        if callable(notify):
            try:
                notify()
            except Exception:
                pass
    
    # Buttons (consistent style via page builder)
    # Row 0: [Paste] [Convert]
    # Paste fills the Thai name and auto-converts immediately.
    # Convert can still be pressed again later for the current text.
    karaoke_paste_btn = make_styled_button(karaoke_form, "SECONDARY", "📋 วาง", width=12)
    karaoke_paste_btn.grid(row=0, column=2, sticky="ew", padx=(0, 4), pady=(0, 10))
    karaoke_convert_btn = make_styled_button(karaoke_form, "PRIMARY", "🔤 แปลง", width=12)
    karaoke_convert_btn.grid(row=0, column=3, sticky="ew", padx=(0, 0), pady=(0, 10))
    karaoke_input.bind("<Return>", lambda e: convert_karaoke())
    
    karaoke_copy_btn = make_styled_button(karaoke_form, "SECONDARY", "📋 Copy", width=12,
        command=lambda: (root.clipboard_clear(), root.clipboard_append(karaoke_result_var.get()), _karaoke_status("คัดลอกแล้ว ✓")))
    karaoke_copy_btn.grid(row=1, column=2, sticky="ew", padx=(0, 4), pady=(0, 8))
    
    karaoke_clear_btn = make_styled_button(karaoke_form, "DANGER", "🧹 Clear", width=12,
        command=lambda: (karaoke_name_var.set(""), karaoke_result_var.set(""), _karaoke_status("")))
    karaoke_clear_btn.grid(row=1, column=3, sticky="ew", padx=(0, 0), pady=(0, 8))
    
    def _thai_to_roman(thai_name):
        import urllib.request
        try:
            body = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "คุณคือผู้ช่วยถอดเสียงภาษาไทยเป็นอักษรโรมันแบบอ่านง่ายสำหรับฝรั่ง ตอบเฉพาะคำอ่านเท่านั้น ห้ามอธิบาย\n\nกฎ:\n- ใช้ตัวสะกดแบบภาษาอังกฤษธรรมชาติ อ่านแล้วออกเสียงใกล้เคียงที่สุด\n- สระสั้น-ยาว ไม่ต้องแยกชัด เช่น ก้าน = Kan (ไม่ใช่ Kaan), จันทร์ = Chan (ไม่ใช่ Chanthr)\n- พยัญชนะต้นใช้ตัวอักษรที่ฝรั่งอ่านออก เช่น จ = Ch/J, ท = T, พ = P, ภ = P, ก = K\n- ตัวสะกดใช้ตัวที่ฝรั่งคุ้น เช่น -น = n, -ด = t/d, -บ = p/b, -ก = k\n- ไม่ต้องใส่วรรณยุกต์\n- ทำให้สั้น กระชับ อ่านง่ายที่สุด"},
                    {"role": "user", "content": f"แปลงชื่อนี้เป็นคำอ่านภาษาอังกฤษ: {thai_name}"},
                ],
                "temperature": 0.1,
            }
            req = urllib.request.Request(
                "http://127.0.0.1:8000/v1/chat/completions",
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": "Bearer local-dev-key", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"ERROR: {e}"
    
    def convert_karaoke():
        name = karaoke_name_var.get().strip()
        if not name:
            _karaoke_status("ใส่ชื่อภาษาไทยก่อน")
            return
        karaoke_convert_btn.config(state="disabled", text="⏳ กำลังแปลง...")
        _karaoke_status("กำลังแปลง...")
        def worker():
            result = _thai_to_roman(name)
            def done():
                karaoke_result_var.set(result)
                karaoke_convert_btn.config(state="normal", text="🔤 แปลง")
                _karaoke_status("แปลงเสร็จ ✓" if not result.startswith("ERROR") else result)
                if not result.startswith("ERROR"):
                    _notify_done()
            root.after(0, done)
        threading.Thread(target=worker, daemon=True).start()
    
    def paste_and_convert():
        """Paste clipboard into the name box, then convert immediately."""
        if not _paste_karaoke_text(replace_all=True):
            _karaoke_status("คลิปบอร์ดว่าง หรือวางไม่ได้")
            return
        _karaoke_status("วางแล้ว — กำลังแปลง...")
        convert_karaoke()

    karaoke_paste_btn.config(command=paste_and_convert)
    karaoke_convert_btn.config(command=convert_karaoke)
    g["karaoke_page"] = karaoke_page
    g["_karaoke_status"] = _karaoke_status
    g["karaoke_log_box"] = karaoke_log_box
    # Karaoke has no selectable entity, so it intentionally has no lock bar.
    g["karaoke_lock_bar"] = None
    
    old_switch = g.get("switch_mode")
    g["karaoke_page"] = karaoke_page
    return karaoke_page
