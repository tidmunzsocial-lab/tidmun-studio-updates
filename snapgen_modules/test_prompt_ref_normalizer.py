# -*- coding: utf-8 -*-
"""Regression tests for Prompt-Ref AI output normalization.

Run:
  .venv312/Scripts/python.exe snapgen_modules/test_prompt_ref_normalizer.py
"""
from __future__ import annotations
import re


def normalize(text: str) -> str:
    raw = (text or "").strip().replace("\r", "")
    raw = re.sub(r"```(?:text)?\s*", "", raw).replace("```", "").strip()
    chunks = [c.strip() for c in re.split(r"\n\s*\n+", raw) if c.strip()]
    if len(chunks) == 1:
        numbered = re.split(r"(?m)^\s*\d{1,2}\s*[\.|\)]\s+", raw)
        chunks = [p.strip() for p in numbered if p.strip()]
    out = []
    for chunk in chunks:
        chunk = re.sub(r"^\s*\d{1,2}\s*[\.|\)]\s*", "", chunk.strip())
        if chunk:
            out.append(chunk)
    if len(out) < 4:
        raise RuntimeError(f"AI returned {len(out)} prompts, expected 3-10 shot prompts plus final storyboard prompt")
    if len(out) > 11:
        out = out[:11]
    shot_count = len(out) - 1
    if shot_count < 3 or shot_count > 10:
        raise RuntimeError(f"AI returned {shot_count} shot prompts, expected 3-10 before storyboard")
    short = [i + 1 for i, chunk in enumerate(out[:-1]) if len(chunk) < 180]
    if short:
        raise RuntimeError("AI returned prompt too short at: " + ", ".join(map(str, short)))

    final = out[-1]
    has_overview_label = bool(re.search(r"รวม\s*ซีน|storyboard|ภาพรวม", final, re.I))
    has_panel_layout = bool(re.search(r"grid|ตาราง|ช่อง|panel", final, re.I))
    if not has_panel_layout:
        raise RuntimeError("AI returned final storyboard prompt without grid/panel layout")
    if not has_overview_label:
        out[-1] = "รวมซีน Storyboard — " + final
    return "\n\n".join(out).strip() + "\n"


def long_shot(n: int) -> str:
    return (f"Wide Shot {n}: เหตุการณ์สำคัญ ตัวละครหลักอยู่กลางเฟรม กล้องค่อย ๆ เคลื่อนเข้า "
            "foreground มีวัตถุประกอบ midground แสดงการกระทำ background เป็นสถานที่ของเรื่อง "
            "แสงธรรมชาติหม่น สีหน้าและภาษากายชัดเจน บรรยากาศตึงเครียดแบบภาพยนตร์ไทย "
            "ใช้เลนส์สมจริงและจัดองค์ประกอบให้ตัวละครหลักเด่นชัด ไม่ถูกฉากหน้าบัง")


# Exact regression: valid grid prompt without the literal words "รวมซีน"/"storyboard".
text = "\n\n".join([long_shot(i) for i in range(1, 11)] + [
    "Single image divided into 5 grid panels, each panel shows one important shot, "
    "ช่องแรกแสดงสถานที่ ช่องกลางแสดงความขัดแย้ง ช่องสุดท้ายแสดงจุด unresolved "
    "ทุกช่องเรียงซ้ายไปขวาบนลงล่างและรวมเหตุการณ์ทั้งฉากไว้ในภาพเดียว"
])
result = normalize(text)
assert "รวมซีน Storyboard — Single image divided" in result
print("PASS: valid panel overview without explicit label is accepted and normalized")

# Invalid final prompt still fails when no grid/panel structure exists.
bad = "\n\n".join([long_shot(i) for i in range(1, 11)] + ["ภาพรวมของเหตุการณ์ทั้งหมดในฉากเดียว"])
try:
    normalize(bad)
except RuntimeError as exc:
    assert "without grid/panel layout" in str(exc)
    print("PASS: final prompt without panel layout is still rejected")
else:
    raise AssertionError("expected missing-grid error")
