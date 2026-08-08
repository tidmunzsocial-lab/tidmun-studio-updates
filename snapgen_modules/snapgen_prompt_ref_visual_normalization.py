# -*- coding: utf-8 -*-
"""Prompt-Ref Visual Bible canonicalization and non-destructive repair patch."""
from __future__ import annotations

from copy import deepcopy

CHARACTER_FIELD_ALIASES = {
    "ดวงต": "ดวงตา",
    "เสื้อผ": "เสื้อผ้า",
}
CHARACTER_CATEGORIES = ("main_characters", "supporting_characters", "animals", "supernatural_entities", "characters")


def _has_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def normalize_character_aliases(item):
    """Canonicalize known GPT typo aliases without letting empty values win."""
    if not isinstance(item, dict):
        return item
    out = dict(item)
    for alias, canonical in CHARACTER_FIELD_ALIASES.items():
        alias_value = out.get(alias)
        canonical_value = out.get(canonical)
        if not _has_value(canonical_value) and _has_value(alias_value):
            out[canonical] = alias_value
        out.pop(alias, None)
    return out


def normalize_breakdown_aliases(parsed):
    """Return a copy with character aliases canonicalized before validation."""
    if not isinstance(parsed, dict):
        return parsed
    out = deepcopy(parsed)
    for category in CHARACTER_CATEGORIES:
        rows = out.get(category)
        if isinstance(rows, list):
            out[category] = [normalize_character_aliases(row) if isinstance(row, dict) else row for row in rows]
    return out


def _list_identity(item):
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "").strip().casefold()
    entity_type = str(item.get("entity_type") or "").strip().casefold()
    return (entity_type, name) if name else None


def merge_preserve_nonempty(existing, repair):
    """Merge repair data without allowing empty repair values to erase existing data."""
    if not _has_value(repair):
        return deepcopy(existing)
    if isinstance(existing, dict) and isinstance(repair, dict):
        result = deepcopy(existing)
        for key, value in repair.items():
            if key in result:
                result[key] = merge_preserve_nonempty(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
    if isinstance(existing, list) and isinstance(repair, list):
        if not repair:
            return deepcopy(existing)
        if all(isinstance(x, dict) and _list_identity(x) for x in existing + repair):
            result = deepcopy(existing)
            positions = {_list_identity(x): idx for idx, x in enumerate(result)}
            for row in repair:
                identity = _list_identity(row)
                if identity in positions:
                    idx = positions[identity]
                    result[idx] = merge_preserve_nonempty(result[idx], row)
                else:
                    positions[identity] = len(result)
                    result.append(deepcopy(row))
            return result
        return deepcopy(repair)
    return deepcopy(repair)


def install_prompt_ref_visual_normalization(g):
    """Patch current Prompt-Ref v4 functions without changing its history architecture."""
    if not isinstance(g, dict) or g.get("_prompt_ref_visual_alias_patch_installed"):
        return False
    original_normalize = g.get("_normalize_prompt_ref_breakdown")
    original_validator = g.get("_prompt_ref_visual_bible_incomplete")
    parse_json = g.get("_parse_bridge_context_json")
    prompt_chat = g.get("_prompt_ref_chat")
    persist = g.get("_persist_prompt_ref_breakdown")
    quality_rules = g.get("_prompt_ref_context_quality_rules")
    schema_text = g.get("_prompt_ref_context_schema_text")
    if not all(callable(fn) for fn in (original_normalize, original_validator, parse_json, prompt_chat, persist, quality_rules, schema_text)):
        return False

    def normalized_breakdown(parsed):
        canonical_input = normalize_breakdown_aliases(parsed)
        normalized = original_normalize(canonical_input)
        return normalize_breakdown_aliases(normalized)

    def visual_bible_incomplete(parsed):
        return original_validator(normalized_breakdown(parsed))

    def audit_prompt_ref_context(reply, story_text=""):
        parsed = normalized_breakdown(parse_json(reply))
        current = __import__("json").dumps({k: v for k, v in parsed.items() if k != "characters"}, ensure_ascii=False)
        audit_prompt = (
            "ตรวจ STORY BREAKDOWN JSON ด้านล่างเทียบกับ FULL STORY/ไฟล์ DOCX ในประวัติเดียวกันอีกครั้ง. "
            "คืน JSON ใหม่ทั้ง object เท่านั้น ห้าม markdown. อย่าเปลี่ยนโครงสร้างหมวด. "
            "ตรวจ coverage และแก้ Character/Entity Visual Bible ให้พร้อมสร้าง Ref ตามกฎทั้งหมด. "
            + quality_rules() + "ใช้ schema นี้เท่านั้น: " + schema_text()
            + "\nCURRENT_STORY_BREAKDOWN_JSON:\n" + current
        )
        repaired = prompt_chat([{"role": "user", "content": audit_prompt}], require_history=True)
        if repaired:
            try:
                repair_obj = normalized_breakdown(parse_json(repaired))
                parsed = normalized_breakdown(merge_preserve_nonempty(parsed, repair_obj))
            except Exception as exc:
                print(f"[SnapGen] Story Breakdown audit fallback to first pass: {exc}")

        if visual_bible_incomplete(parsed):
            current = __import__("json").dumps({k: v for k, v in parsed.items() if k != "characters"}, ensure_ascii=False)
            visual_repair_prompt = (
                "VISUAL BIBLE REPAIR REQUIRED. JSON นี้ยังมี entity ที่ needs_ref=true แต่รายละเอียดภาพไม่พอสร้าง Ref. "
                "อ้างอิง FULL STORY/ไฟล์ DOCX ที่อยู่ในประวัติเดียวกัน ห้ามเปลี่ยนชื่อ หมวด entity_type story_role importance needs_ref หรือเหตุการณ์. "
                "เติม/แก้เฉพาะรายละเอียดภาพให้เฉพาะเจาะจงและสมเหตุผล. สำหรับมนุษย์ต้องมี อายุ เพศ รูปร่าง ส่วนสูง สีผิว ทรงผม ใบหน้า ดวงตา เสื้อผ้า ลักษณะเด่น visual_identity ครบ. "
                "ห้ามใช้ 'ไม่ระบุ' หรือคำกว้าง ๆ เช่น 'ชายไทยทั่วไป'. สิ่งที่บทไม่ได้ระบุให้เลือกแบบที่เหมาะกับยุค สถานที่ บทบาท อาชีพ ฐานะ ครอบครัว และเหตุการณ์หลัก แล้วลงท้าย field นั้นด้วย '(สมมุติเพื่อภาพ)'. "
                "evidence ต้องคงเป็นข้อเท็จจริงจากบทเท่านั้น; assumptions ใช้บันทึกสิ่งที่สมมุติ. เสื้อผ้าเลือกชุดหลักเพียงชุดเดียว. "
                "คืน JSON object เต็มตาม schema เท่านั้น ห้าม markdown. schema: " + schema_text()
                + "\nCURRENT_STORY_BREAKDOWN_JSON:\n" + current
            )
            repaired_visual = prompt_chat([{"role": "user", "content": visual_repair_prompt}], require_history=True)
            if repaired_visual:
                try:
                    repair_obj = normalized_breakdown(parse_json(repaired_visual))
                    parsed = normalized_breakdown(merge_preserve_nonempty(parsed, repair_obj))
                except Exception as exc:
                    print(f"[SnapGen] Visual Bible repair fallback to audit result: {exc}")
        persist(parsed)
        return parsed

    g["_normalize_prompt_ref_breakdown"] = normalized_breakdown
    g["_prompt_ref_visual_bible_incomplete"] = visual_bible_incomplete
    g["_audit_prompt_ref_context"] = audit_prompt_ref_context
    g["_prompt_ref_visual_alias_patch_installed"] = True
    return True
