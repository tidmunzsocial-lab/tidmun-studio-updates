# -*- coding: utf-8 -*-
"""Forbidden-words editor for Video prompts.

Adds a small settings button near the Video page that opens a popup where
users can edit, enable/disable, and push the forbidden-word list to GitHub.
"""
from __future__ import annotations

import json, os, subprocess, sys, time, urllib.request
from pathlib import Path
from tkinter import Toplevel, Frame, Label, Entry, Button, Listbox, Scrollbar, Checkbutton, BooleanVar, StringVar, messagebox, END

REPO = "tidmunzsocial-lab/tidmun-studio-updates"
BRANCH = "main"


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"enabled": True, "match_case": False, "words": []}


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))



def _fetch_from_github(json_path: Path) -> bool:
    """Download latest forbidden words from GitHub on startup."""
    try:
        url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/assets/video_forbidden_words.json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict) and "words" in data:
            _save_json(json_path, data)
            print(f"[SnapGen] forbidden words fetched from GitHub: {len(data['words'])} words")
            return True
    except Exception as e:
        print(f"[SnapGen] forbidden words fetch skipped: {e}")
    return False

def _publish_to_github(json_path: Path, log_fn):
    """Commit and push video_forbidden_words.json to the update repository."""
    try:
        import subprocess
        # Find a git repo that contains this file (project root)
        project_root = json_path.parent.parent
        git_dir = project_root / ".git"
        if not git_dir.is_dir():
            log_fn("⚠️  ไม่พบ Git repository ในโปรเจค — อัปเดต GitHub ไม่ได้")
            return False

        # Stage only the forbidden words file
        subprocess.run(["git", "-C", str(project_root), "add", str(json_path)],
                       capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        # Commit
        r = subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "Update video forbidden words"],
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace"
        )
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr).lower():
            err = (r.stderr or "")[-300:]
            log_fn(f"⚠️  Git commit ไม่สำเร็จ: {err}")
            return False
        # Push
        r = subprocess.run(
            ["git", "-C", str(project_root), "push", "origin", BRANCH],
            capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace"
        )
        if r.returncode != 0:
            err = (r.stderr or "")[-300:]
            log_fn(f"⚠️  Git push ไม่สำเร็จ: {err}")
            return False
        log_fn("✅ อัปเดต GitHub สำเร็จ")
        return True
    except Exception as e:
        log_fn(f"⚠️  GitHub update error: {e}")
        return False


def open_editor(root, json_path, reload_fn=None):
    json_path = Path(json_path)
    data = _load_json(json_path)

    win = Toplevel(root)
    win.title("จัดการคำต้องห้ามในช่องวิดีโอ")
    win.geometry("500x520")
    win.transient(root)
    win.grab_set()

    Label(win, text="คำต้องห้าม ( forbidden words )", font=("Leelawadee UI", 12, "bold")).pack(pady=10)

    enabled_var = BooleanVar(value=data.get("enabled", True))
    case_var = BooleanVar(value=data.get("match_case", False))

    Checkbutton(win, text="เปิดใช้งานไฮไลท์", variable=enabled_var).pack(anchor="w", padx=20)
    Checkbutton(win, text="ตรงตัวพิมพ์เล็ก/ใหญ่", variable=case_var).pack(anchor="w", padx=20)

    frame = Frame(win)
    frame.pack(fill="both", expand=True, padx=20, pady=10)

    scrollbar = Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")

    lb = Listbox(frame, yscrollcommand=scrollbar.set, font=("Leelawadee UI", 11))
    lb.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=lb.yview)

    for w in data.get("words", []):
        lb.insert(END, w)

    entry_var = StringVar()
    entry = Entry(win, textvariable=entry_var, font=("Leelawadee UI", 11))
    entry.pack(fill="x", padx=20, pady=5)
    entry.bind("<Return>", lambda _e: add_word())

    status_var = StringVar(value="พร้อม")
    status = Label(win, textvariable=status_var, fg="gray", font=("Leelawadee UI", 9))
    status.pack(pady=2)

    def set_status(msg, color="gray"):
        status_var.set(msg)
        status.config(fg=color)

    def add_word():
        word = entry_var.get().strip()
        if not word:
            return
        items = [lb.get(i) for i in range(lb.size())]
        if word.lower() in [w.lower() for w in items]:
            set_status(f"'{word}' มีอยู่แล้ว", "orange")
            return
        lb.insert(END, word)
        entry_var.set("")
        set_status(f"เพิ่ม '{word}' แล้ว", "green")

    def remove_word():
        sel = lb.curselection()
        if not sel:
            set_status("เลือกคำที่จะลบก่อน", "orange")
            return
        word = lb.get(sel[0])
        lb.delete(sel[0])
        set_status(f"ลบ '{word}' แล้ว", "green")

    def save_and_push():
        words = [lb.get(i).strip() for i in range(lb.size()) if lb.get(i).strip()]
        new_data = {
            "enabled": enabled_var.get(),
            "match_case": case_var.get(),
            "words": words,
        }
        _save_json(json_path, new_data)
        set_status("💾 บันทึกไฟล์แล้ว — กำลังอัปเดต GitHub...", "blue")
        win.update()

        _publish_to_github(json_path, lambda m: set_status(m, "blue"))

        if callable(reload_fn):
            try:
                reload_fn()
            except Exception:
                pass
        set_status("✅ เสร็จสิ้น", "green")

    btn_frame = Frame(win)
    btn_frame.pack(fill="x", padx=20, pady=5)

    Button(btn_frame, text="➕ เพิ่ม", command=add_word, bg="#16A34A", fg="white").pack(side="left", padx=3)
    Button(btn_frame, text="🗑 ลบ", command=remove_word, bg="#DC2626", fg="white").pack(side="left", padx=3)

    Button(win, text="💾 บันทึก + อัปเดต GitHub", command=save_and_push,
           bg="#2563EB", fg="white", font=("Leelawadee UI", 10, "bold"), padx=20, pady=8).pack(pady=15)


def install_button(root, g, json_path):
    """Add a small 'forbidden words' button that only shows on Video page."""
    try:
        import tkinter as tk
        json_path = Path(json_path)
        # Fetch latest from GitHub on every startup
        _fetch_from_github(json_path)

        def on_click():
            reload = g.get("reload_video_forbidden_words")
            open_editor(root, json_path, reload_fn=reload)

        parent = g.get("slots") or root
        btn = tk.Button(
            parent,
            text="⚠️",
            command=on_click,
            bg="#DC2626",
            fg="white",
            font=("Leelawadee UI", 9, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=4,
        )

        def _is_video_mode():
            try:
                cur = g.get("current_mode")
                if cur is not None and hasattr(cur, "get"):
                    return str(cur.get()).lower() == "video"
            except Exception:
                pass
            return True

        def reposition(*_):
            try:
                w = parent.winfo_width()
                if _is_video_mode():
                    btn.place(relx=1.0, x=-10, y=4, anchor='ne')
                else:
                    btn.place_forget()
            except Exception:
                pass

        # Start visible only if in video mode
        if _is_video_mode():
            btn.place(relx=1.0, x=-10, y=4, anchor='ne')
        else:
            btn.place_forget()

        parent.bind("<Configure>", lambda _e: reposition(), add="+")
        reposition()

        # Hook into switch_mode so button hides on non-video pages
        _old_switch = g.get("switch_mode")
        def _patched_switch(mode, *a, **kw):
            try:
                result = _old_switch(mode, *a, **kw) if _old_switch else None
            except Exception:
                result = None
            try:
                if str(mode).lower() == "video":
                    w = parent.winfo_width()
                    btn.place(relx=1.0, x=-10, y=4, anchor='ne')
                else:
                    btn.place_forget()
            except Exception:
                pass
            return result
        g["switch_mode"] = _patched_switch

        g["_forbidden_words_btn"] = btn
        return btn
    except Exception as e:
        print(f"[SnapGen] forbidden words button install failed: {e}")
        return None
