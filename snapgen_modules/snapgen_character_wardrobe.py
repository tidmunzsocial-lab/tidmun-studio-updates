# -*- coding: utf-8 -*-
"""Story-driven Character Reference wardrobe helpers.

This module is intentionally pure: no UI and no Bridge calls. Prompt-Ref remains
responsible for story understanding; this layer turns the extracted story facts
into a stable wardrobe contract and keeps old Context files compatible.
"""
from __future__ import annotations

import re
from copy import deepcopy

_UNKNOWN = {"", "ไม่ระบุ", "unknown", "none", "null"}
_INFER_MARK = "(สมมุติเพื่อภาพ)"
_CLOTHING_TERMS = (
    "เสื้อ", "กางเกง", "กระโปรง", "ชุด", "รองเท้า", "แตะ", "สูท", "เครื่องแบบ",
    "uniform", "shirt", "pants", "trousers", "skirt", "dress", "shoe", "sandal",
)


def _text(value):
    return " ".join(str(value or "").split()).strip()


def _known(value):
    return bool(_text(value)) and _text(value).casefold() not in _UNKNOWN


def _joined(value):
    if isinstance(value, (list, tuple)):
        return " | ".join(_text(x) for x in value if _text(x))
    return _text(value)


def _evidence_mentions_clothes(entity):
    evidence = _joined(entity.get("evidence") if isinstance(entity, dict) else "").casefold()
    return any(term.casefold() in evidence for term in _CLOTHING_TERMS)


def _inference_context(entity, story):
    parts = []
    for label, value in (
        ("ยุค", story.get("era")),
        ("พื้นที่", story.get("country_or_region") or story.get("main_location")),
        ("อากาศ", story.get("weather_context") or story.get("climate")),
        ("วัย", entity.get("อายุ")),
        ("เพศ/การนำเสนอ", entity.get("เพศ")),
        ("อาชีพ", entity.get("อาชีพ")),
        ("ฐานะ", entity.get("ฐานะ")),
        ("บทบาท", entity.get("story_role") or entity.get("บทบาท")),
    ):
        if _known(value):
            parts.append(f"{label}={_text(value)}")
    summary = _text(story.get("summary"))
    if summary:
        parts.append("สถานการณ์=" + summary[:180])
    return "; ".join(parts)


def _world_flags(entity, story):
    world_blob = " ".join(
        _text(x) for x in (
            story.get("era"), story.get("country_or_region"), story.get("main_location"), story.get("summary"),
        ) if _text(x)
    ).casefold()
    entity_blob = " ".join(
        _joined(x) for x in (
            entity.get("อาชีพ"), entity.get("ฐานะ"), entity.get("story_role"), entity.get("บทบาท"),
            entity.get("เสื้อผ้า"), entity.get("evidence"),
        ) if _joined(x)
    ).casefold()
    thai = any(x in world_blob for x in ("ไทย", "thailand", "กรุงเทพ", "เชียง", "อีสาน", "ชนบท"))
    rural = any(x in world_blob for x in ("ชนบท", "หมู่บ้าน", "ไร่", "นา", "สวน", "farm", "rural"))
    # Uniform/special-role inference must belong to this character, never to a
    # different person merely mentioned in the whole-story summary.
    school = any(x in entity_blob for x in ("นักเรียน", "โรงเรียน", "student", "school"))
    monk = any(x in entity_blob for x in ("พระสงฆ์", "หลวงพ่อ", "พระภิกษุ", "monk"))
    funeral = any(x in entity_blob for x in ("งานศพ", "ไว้ทุกข์", "funeral", "mourning"))
    return thai, rural, school, monk, funeral

def _infer_default_outfit(entity, story):
    thai, rural, school, monk, funeral = _world_flags(entity, story)
    era = _text(story.get("era")) or "ยุคของเรื่อง"
    location = _text(story.get("country_or_region") or story.get("main_location")) or "พื้นที่ของเรื่อง"
    climate = _text(story.get("weather_context") or story.get("climate"))

    if monk:
        return {
            "top": "จีวรพระสงฆ์ตามบริบทไทย",
            "bottom": "สบงพระสงฆ์เข้าชุด",
            "footwear": "เท้าเปล่าหรือรองเท้าแตะเรียบง่ายตามสถานการณ์",
            "outerwear": "",
            "accessories": "ไม่มีเครื่องประดับแฟชั่น",
            "colors": "โทนกรัก/ส้มหม่นตามจีวร",
            "materials": "ผ้าฝ้ายหรือผ้าจีวรเนื้อเรียบ",
            "condition": "ใช้งานจริง สะอาดพอสมควร ไม่แฟชั่นจัด",
            "overall_style": "เครื่องแต่งกายพระสงฆ์ที่สมจริงกับเรื่อง",
        }
    if school:
        return {
            "top": "เสื้อนักเรียนที่ตรงกับยุคและพื้นที่ของเรื่อง",
            "bottom": "กางเกงหรือกระโปรงนักเรียนตามเพศ/การนำเสนอที่บทสนับสนุน",
            "footwear": "รองเท้านักเรียนที่ตรงกับยุค",
            "outerwear": "",
            "accessories": "อุปกรณ์นักเรียนเท่าที่สมเหตุผล ไม่เพิ่มแฟชั่น",
            "colors": "สีเครื่องแบบตามบริบทสถานศึกษา",
            "materials": "ผ้าเครื่องแบบใช้งานจริง",
            "condition": "ชุดใช้งานประจำวัน ไม่เนี้ยบเกินฐานะ",
            "overall_style": "เครื่องแบบนักเรียนตามโลกของเรื่อง",
        }
    if funeral:
        return {
            "top": "เสื้อสุภาพเรียบง่ายสำหรับงานศพ",
            "bottom": "กางเกงขายาวหรือกระโปรงสุภาพ",
            "footwear": "รองเท้าสุภาพเรียบ ไม่มีสีฉูดฉาด",
            "outerwear": "",
            "accessories": "เครื่องประดับน้อยที่สุด",
            "colors": "ดำ เทาเข้ม หรือสีไว้ทุกข์ตามวัฒนธรรมของเรื่อง",
            "materials": "ผ้าธรรมดาไม่มันวาว",
            "condition": "สะอาด สุภาพ",
            "overall_style": "ชุดไว้ทุกข์ที่ไม่แฟชั่นเกินโลกของเรื่อง",
        }

    if thai and rural:
        top = "เสื้อยืดหรือเสื้อเชิ้ตผ้าฝ้ายเรียบ ใช้งานประจำวัน ไม่พิมพ์ลายแฟชั่นสมัยใหม่"
        bottom = "กางเกงขายาวผ้าฝ้าย/ผ้าทำงานทรงธรรมดาที่เหมาะกับชนบท"
        footwear = "รองเท้าแตะหรือรองเท้าใช้งานเรียบง่าย"
        style = f"ชุดชาวบ้าน/ครอบครัวทั่วไปที่เป็นไปได้สูงใน {location} ช่วง {era}"
    elif thai:
        top = "เสื้อผ้าท่อนบนเรียบง่ายตามวัยและฐานะของตัวละคร ไม่ตามแฟชั่นร่วมสมัยเกินยุค"
        bottom = "กางเกงขายาวหรือกระโปรงทรงธรรมดาตามบริบทตัวละคร"
        footwear = "รองเท้าหรือรองเท้าแตะใช้งานประจำวันที่เหมาะกับสถานที่"
        style = f"ชุดคนไทยใช้งานจริงที่เข้ากับ {era} และ {location}"
    else:
        top = "เสื้อท่อนบนใช้งานประจำวันที่ตรงกับยุค วัฒนธรรม วัย และฐานะของตัวละคร"
        bottom = "กางเกงหรือกระโปรงใช้งานประจำวันที่ตรงกับยุคและวัฒนธรรม"
        footwear = "รองเท้าใช้งานประจำวันที่ตรงกับยุค สถานที่ และฐานะ"
        style = f"ชุดธรรมดาที่มีความเป็นไปได้สูงใน {location} ช่วง {era} ไม่ใช่แฟชั่นสุ่ม"

    if climate:
        style += f" และเหมาะกับสภาพอากาศ {climate}"
    return {
        "top": top,
        "bottom": bottom,
        "footwear": footwear,
        "outerwear": "เฉพาะเมื่อสภาพอากาศหรือบทต้องการ มิฉะนั้นไม่มี",
        "accessories": "เฉพาะของใช้/เครื่องประดับที่เข้ากับบทและฐานะ มิฉะนั้นน้อยที่สุด",
        "colors": "สีใช้งานจริงหม่นหรือเป็นกลาง สอดคล้องยุคและฐานะ ไม่เลือกสีแฟชั่นสุ่ม",
        "materials": "วัสดุเสื้อผ้าที่หาได้จริงในยุคและพื้นที่ เช่น ผ้าฝ้าย/ผ้าทอธรรมดาตามบริบท",
        "condition": "สภาพใช้งานจริง สอดคล้องฐานะ อาชีพ และสถานการณ์ ไม่ใหม่เนี้ยบเกินเหตุ",
        "overall_style": style,
    }


def _outfit_from_text(clothes, entity, story):
    """Preserve explicit story clothing verbatim and fill unseen full-body parts conservatively."""
    clothes = _text(clothes)
    base = _infer_default_outfit(entity, story)
    if not clothes:
        return base
    lower = clothes.casefold()
    top_terms = ("เสื้อ", "shirt", "blouse", "jacket", "จีวร")
    bottom_terms = ("กางเกง", "กระโปรง", "pants", "trousers", "skirt", "สบง")
    shoe_terms = ("รองเท้า", "แตะ", "shoe", "sandal", "boot")
    if any(x in lower for x in top_terms):
        base["top"] = clothes
    if any(x in lower for x in bottom_terms):
        base["bottom"] = clothes
    if any(x in lower for x in shoe_terms):
        base["footwear"] = clothes
    base["overall_style"] = clothes
    return base


def normalize_character_wardrobe(entity, story=None):
    """Return a backwards-compatible wardrobe contract for one human character."""
    entity = entity if isinstance(entity, dict) else {}
    story = story if isinstance(story, dict) else {}
    existing = entity.get("wardrobe") if isinstance(entity.get("wardrobe"), dict) else {}
    existing_default = existing.get("default_outfit") if isinstance(existing.get("default_outfit"), dict) else {}

    clothes = _text(entity.get("เสื้อผ้า") or entity.get("clothes"))
    source = _text(existing.get("wardrobe_source") or entity.get("wardrobe_source")).lower()
    if source not in ("explicit", "inferred"):
        source = "explicit" if clothes and _INFER_MARK not in clothes and _evidence_mentions_clothes(entity) else "inferred"

    inferred = _outfit_from_text(clothes, entity, story)
    default = deepcopy(inferred)
    for key in tuple(default):
        if _known(existing_default.get(key)):
            default[key] = _text(existing_default.get(key))

    variants = existing.get("variants") if isinstance(existing.get("variants"), list) else []
    if not variants:
        variants = entity.get("outfit_variants") if isinstance(entity.get("outfit_variants"), list) else []

    reason = _text(existing.get("wardrobe_reason") or entity.get("wardrobe_reason"))
    if not reason:
        if source == "explicit":
            reason = "ใช้เสื้อผ้าที่บทระบุจริงเป็นหลัก และเติมเฉพาะส่วนที่จำเป็นต่อภาพเต็มตัวโดยไม่ขัดกับบท"
        else:
            context = _inference_context(entity, story)
            reason = "อนุมานชุดธรรมดาที่มีความเป็นไปได้สูงที่สุดจากบริบทของเรื่อง"
            if context:
                reason += ": " + context[:300]

    return {
        "default_outfit": default,
        "wardrobe_source": source,
        "wardrobe_reason": reason,
        "variants": variants,
    }


def apply_character_wardrobe(entity, story=None):
    """Mutate one character dict with wardrobe fields while preserving old keys."""
    if not isinstance(entity, dict):
        return entity
    wardrobe = normalize_character_wardrobe(entity, story)
    entity["wardrobe"] = wardrobe
    entity["wardrobe_source"] = wardrobe["wardrobe_source"]
    entity["wardrobe_reason"] = wardrobe["wardrobe_reason"]
    outfit = wardrobe["default_outfit"]
    if not _known(entity.get("เสื้อผ้า")):
        entity["เสื้อผ้า"] = outfit.get("overall_style") or "ชุดธรรมดาตามบริบทเรื่อง " + _INFER_MARK
        if wardrobe["wardrobe_source"] == "inferred" and _INFER_MARK not in entity["เสื้อผ้า"]:
            entity["เสื้อผ้า"] += " " + _INFER_MARK
    return entity


def wardrobe_prompt_text(entity, story=None):
    """One immutable outfit description for Front / 3/4 / Full-body Ref views."""
    wardrobe = normalize_character_wardrobe(entity, story)
    outfit = wardrobe["default_outfit"]
    order = (
        ("top", "เสื้อ"), ("bottom", "ท่อนล่าง"), ("footwear", "รองเท้า"),
        ("outerwear", "เสื้อคลุม"), ("accessories", "เครื่องประกอบ"),
        ("colors", "สี"), ("materials", "วัสดุ"), ("condition", "สภาพ"),
        ("overall_style", "ภาพรวม"),
    )
    body = "; ".join(f"{label}: {_text(outfit.get(key))}" for key, label in order if _known(outfit.get(key)))
    return (
        body
        + f". source={wardrobe['wardrobe_source']}. เหตุผล: {wardrobe['wardrobe_reason']}. "
        + "WARDROBE LOCK: ใช้คำบรรยายชุดก้อนนี้ชุดเดียวเหมือนกัน 100% ใน Front view, 3/4 view และ Full-body view; "
          "ห้ามออกแบบชุดใหม่ ห้ามเปลี่ยนสี วัสดุ รองเท้า หรือ accessories ระหว่างมุม."
    )
