# -*- coding: utf-8 -*-
"""Prompt Context tools for SnapGen.
Standalone on purpose: keep snapgen_gui_v2.py launcher thin.
"""
import json
import time
from pathlib import Path

from snapgen_character_visual_bible import canonicalize_context, missing_character_fields

UNKNOWN_VALUES = {"", "ไม่ระบุ", "unknown", "null", "None", None}
CHAR_FIELDS = ["อายุ", "เพศ", "สีผิว", "ทรงผม", "ใบหน้า", "เสื้อผ้า", "ลักษณะเด่น"]


def paths(base):
    base = Path(base)
    return {
        "master": base / "context_master.json",
        "snapshot": base / "context_master.last.json",
        "ref_json": base / "prompt_ref_context.json",
        "ref_txt": base / "prompt_ref_context.txt",
    }


def load_context_any(base):
    ps = paths(base)
    for p in [ps["master"], ps["ref_json"]]:
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    try:
        txt = ps["ref_txt"].read_text(encoding="utf-8")
    except Exception:
        txt = ""
    return {"version": 1, "story": {"raw": txt}, "characters": [], "locations": [], "props": [], "scene_map": []}


def invent_missing_char_detail(ch, field):
    """Deprecated compatibility hook; semantic defaults are forbidden."""
    return ""


def normalize_context_master(base, data=None, invent=False):
    """Legacy load boundary: canonicalize structure once without semantic inference."""
    data = data if isinstance(data, dict) else load_context_any(base)
    master = canonicalize_context(data)
    master["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return master


def context_health(base, data=None):
    m = normalize_context_master(base, data, invent=False)
    issues = []
    total = 0
    ok = 0
    for ch in m.get("characters", []):
        if not isinstance(ch, dict):
            continue
        missing = missing_character_fields(ch)
        checked = 1 + (17 if str(ch.get("entity_type") or "").casefold() == "human" and ch.get("needs_ref") else 0)
        total += checked
        ok += max(0, checked - len(missing))
        issues.extend(f"{ch.get('name') or '(ไม่มีชื่อ)'} ไม่มี {field}" for field in missing)
    for key, msg in (("locations", "ไม่มีสถานที่"), ("props", "ไม่มี props"), ("scene_map", "ไม่มี scene map")):
        total += 1
        if m.get(key):
            ok += 1
        else:
            issues.append(msg)
    score = int((ok / total) * 100) if total else 0
    return score, issues, m

def write_context_master(base, data=None, invent=False, sync_ref=True):
    """Normalize and persist one canonical Context for every SnapGen page."""
    ps = paths(base)
    old = ps["master"].read_text(encoding="utf-8") if ps["master"].exists() else ""
    if old:
        ps["snapshot"].write_text(old, encoding="utf-8")
    master = normalize_context_master(base, data=data, invent=invent)
    encoded = json.dumps(master, ensure_ascii=False, indent=2) + "\n"
    ps["master"].write_text(encoded, encoding="utf-8")
    if sync_ref:
        ps["ref_json"].write_text(encoded, encoding="utf-8")
    return master


def context_diff_text(base):
    ps = paths(base)
    if not ps["snapshot"].exists() or not ps["master"].exists():
        return "ยังไม่มี snapshot สำหรับเทียบ — กด Normalize ก่อนอย่างน้อย 2 ครั้ง"
    try:
        old = json.loads(ps["snapshot"].read_text(encoding="utf-8"))
        new = json.loads(ps["master"].read_text(encoding="utf-8"))
    except Exception as e:
        return f"อ่าน diff ไม่ได้: {e}"
    lines = []

    def names(x, key):
        return {i.get("name") for i in x.get(key, []) if isinstance(i, dict) and i.get("name")}

    for key, label in [("characters", "ตัวละคร"), ("locations", "สถานที่"), ("props", "Prop")]:
        add = sorted(names(new, key) - names(old, key))
        rem = sorted(names(old, key) - names(new, key))
        if add:
            lines.append(f"เพิ่ม{label}: " + ", ".join(add))
        if rem:
            lines.append(f"ลบ{label}: " + ", ".join(rem))
    return "\n".join(lines) if lines else "Context ไม่เปลี่ยนในระดับชื่อรายการ"


def context_preview_text(base):
    score, issues, m = context_health(base, load_context_any(base))
    return "\n".join([
        f"Context Score: {score}%",
        f"Characters: {len(m.get('characters', []))} | Locations: {len(m.get('locations', []))} | Props: {len(m.get('props', []))} | Scenes: {len(m.get('scene_map', []))}",
        "",
        "ขาด / ควรเติม:",
        *(issues[:30] or ["พร้อมใช้"]),
    ])


def prompt_preview_text(base):
    m = normalize_context_master(base, load_context_any(base), invent=False)
    lines = ["Prompt Preview Source", "", "Characters:"]
    for ch in m.get("characters", [])[:5]:
        appearance = ch.get("appearance") if isinstance(ch.get("appearance"), dict) else {}
        wardrobe = ch.get("wardrobe") if isinstance(ch.get("wardrobe"), dict) else {}
        lines.append(f"- {ch.get('name')}: {appearance.get('age')} | {appearance.get('face')} | {wardrobe.get('overall_style') or wardrobe.get('top') or ''}")
    lines += ["", "Scenes:"]
    for sc in m.get("scene_map", [])[:5]:
        if isinstance(sc, dict):
            lines.append(f"- {sc.get('place') or sc.get('location')}: {sc.get('note') or sc.get('summary') or ''}")
    return "\n".join(lines)


def install(globals_dict):
    """Expose old function names used by snapgen_gui_v2.py patch code."""
    base = Path(globals_dict.get("BASE", Path.cwd()))
    globals_dict.update({
        "_load_context_any": lambda: load_context_any(base),
        "_normalize_context_master": lambda data=None, invent=False: normalize_context_master(base, data, invent),
        "_context_health": lambda data=None: context_health(base, data),
        "_write_context_master": lambda data=None, invent=False: write_context_master(base, data, invent),
        "_context_diff_text": lambda: context_diff_text(base),
        "_context_preview_text": lambda: context_preview_text(base),
        "_prompt_preview_text": lambda: prompt_preview_text(base),
    })
