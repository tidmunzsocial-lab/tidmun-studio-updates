# -*- coding: utf-8 -*-
"""Story-driven Character Reference wardrobe helpers."""
from __future__ import annotations

import re
from copy import deepcopy

_UNKNOWN = {"", "ไม่ระบุ", "unknown", "none", "null"}
_INFER_MARK = "(สมมุติเพื่อภาพ)"
_CLOTHING_TERMS = (
    "เสื้อ", "กางเกง", "กระโปรง", "ผ้าถุง", "ชุด", "รองเท้า", "แตะ", "สูท", "เครื่องแบบ",
    "uniform", "shirt", "pants", "trousers", "skirt", "dress", "shoe", "sandal", "robe",
)
_HUMANOID_TERMS = ("มนุษย์", "คน", "ชาย", "หญิง", "ร่างคน", "humanoid", "human-like", "humanlike")
_COLOR_TERMS = ("ดำ", "ขาว", "เทา", "น้ำตาล", "ครีม", "แดง", "เขียว", "น้ำเงิน", "กรม", "ฟ้า", "เหลือง", "ส้ม", "ม่วง", "ชมพู", "ซีด", "หม่น")
_MATERIAL_TERMS = ("ผ้าฝ้าย", "ฝ้าย", "ผ้าลินิน", "ลินิน", "ผ้ายีนส์", "ยีนส์", "ผ้าไหม", "ไหม", "ผ้าทอ", "หนัง", "โพลีเอสเตอร์")


def _text(value):
    return " ".join(str(value or "").split()).strip()


def _known(value):
    return bool(_text(value)) and _text(value).casefold() not in _UNKNOWN


def _joined(value):
    if isinstance(value, (list, tuple, set)):
        return " | ".join(_text(x) for x in value if _text(x))
    return _text(value)


def _entity_type(entity):
    raw = _text(entity.get("entity_type") or entity.get("type") or "human").casefold()
    if raw in {"animal", "animal_group"}:
        return "animal"
    if raw in {"supernatural", "supernatural_entity", "supernatural_unknown", "ghost", "spirit"}:
        return "supernatural"
    return "human"


def _evidence_mentions_clothes(entity):
    evidence = _joined(entity.get("evidence") if isinstance(entity, dict) else "").casefold()
    return any(term.casefold() in evidence for term in _CLOTHING_TERMS)


def _explicit_clothes(entity):
    clothes = _text(entity.get("เสื้อผ้า") or entity.get("clothes"))
    if not clothes or clothes.casefold() in _UNKNOWN or _INFER_MARK in clothes:
        return ""
    return clothes if _evidence_mentions_clothes(entity) else ""


def _is_humanoid_supernatural(entity):
    identity = " ".join(_text(entity.get(k)) for k in ("visual_identity", "ลักษณะเด่น", "story_role") if _text(entity.get(k))).casefold()
    return any(term.casefold() in identity for term in _HUMANOID_TERMS)


def _entity_location_context(entity):
    for key in ("location_context", "current_location", "location", "สถานที่", "place", "workplace", "home_context"):
        value = entity.get(key)
        if isinstance(value, dict):
            value = value.get("name") or value.get("place") or value.get("location")
        if isinstance(value, (list, tuple, set)):
            value = " / ".join(_text(x) for x in value if _text(x))
        if _known(value):
            return _text(value)
    evidence = _joined(entity.get("evidence"))
    role = _text(entity.get("story_role") or entity.get("บทบาท"))
    # Entity-owned role/evidence is safe context; do not inherit main_location blindly.
    hints = []
    for needle in ("วัด", "โรงเรียน", "มหาวิทยาลัย", "โรงพยาบาล", "ไร่", "นา", "สวน", "โรงงาน", "สำนักงาน", "บ้าน", "ชุมชน", "พิธี"):
        if needle in evidence or needle in role:
            hints.append(needle)
    return " / ".join(dict.fromkeys(hints))


def _inference_context(entity, story):
    parts = []
    entity_place = _entity_location_context(entity)
    for label, value in (
        ("ยุค", story.get("era")),
        ("ประเทศ/ภูมิภาค", story.get("country_or_region")),
        ("บริบทสถานที่ของตัวละคร", entity_place),
        ("อากาศ", story.get("weather_context") or story.get("climate")),
        ("วัย", entity.get("อายุ")),
        ("เพศ/การนำเสนอ", entity.get("เพศ")),
        ("อาชีพ", entity.get("อาชีพ")),
        ("ฐานะ", entity.get("ฐานะ")),
        ("บทบาท", entity.get("story_role") or entity.get("บทบาท")),
    ):
        if _known(value):
            parts.append(f"{label}={_text(value)}")
    return "; ".join(parts)


def _world_flags(entity, story):
    world_blob = " ".join(_text(x) for x in (story.get("era"), story.get("country_or_region"), story.get("climate"), story.get("weather_context")) if _text(x)).casefold()
    entity_blob = " ".join(_joined(x) for x in (entity.get("อาชีพ"), entity.get("ฐานะ"), entity.get("story_role"), entity.get("บทบาท"), entity.get("เสื้อผ้า"), entity.get("evidence"), _entity_location_context(entity)) if _joined(x)).casefold()
    thai = any(x in world_blob + " " + entity_blob for x in ("ไทย", "thailand", "กรุงเทพ", "เชียง", "อีสาน"))
    rural = any(x in entity_blob for x in ("ชนบท", "หมู่บ้าน", "ไร่", "นา", "สวน", "เกษตร", "farm", "rural"))
    school = any(x in entity_blob for x in ("นักเรียน", "โรงเรียน", "student", "school"))
    monk = any(x in entity_blob for x in ("พระสงฆ์", "หลวงพ่อ", "พระภิกษุ", "monk"))
    funeral = any(x in entity_blob for x in ("งานศพ", "ไว้ทุกข์", "funeral", "mourning"))
    ritual = any(x in entity_blob for x in ("ร่างทรง", "ประกอบพิธี", "พิธี", "medium", "ritual"))
    return thai, rural, school, monk, funeral, ritual


def _infer_default_outfit(entity, story):
    thai, rural, school, monk, funeral, ritual = _world_flags(entity, story)
    era = _text(story.get("era")) or "ยุคของเรื่อง"
    region = _text(story.get("country_or_region")) or "วัฒนธรรมของเรื่อง"
    entity_place = _entity_location_context(entity)
    climate = _text(story.get("weather_context") or story.get("climate"))

    if monk:
        return {"top": "จีวรพระสงฆ์ตามบริบทไทย", "bottom": "สบงพระสงฆ์เข้าชุด", "footwear": "เท้าเปล่าหรือรองเท้าแตะเรียบง่ายตามสถานการณ์", "outerwear": "", "accessories": "ไม่มีเครื่องประดับแฟชั่น", "colors": "โทนกรัก/ส้มหม่นตามจีวร", "materials": "ผ้าจีวรเนื้อเรียบ", "condition": "ใช้งานจริง สะอาดพอสมควร", "overall_style": "เครื่องแต่งกายพระสงฆ์ที่สมจริงกับวัด/ชุมชนและยุคของเรื่อง"}
    if school:
        return {"top": "เสื้อนักเรียนที่ตรงกับยุคและสถานศึกษาของตัวละคร", "bottom": "กางเกงหรือกระโปรงนักเรียนตามหลักฐานเพศ/การนำเสนอ", "footwear": "รองเท้านักเรียนที่ตรงกับยุค", "outerwear": "", "accessories": "อุปกรณ์นักเรียนเท่าที่บท/บริบทตัวละครรองรับ", "colors": "สีเครื่องแบบตามบริบทสถานศึกษา", "materials": "ผ้าเครื่องแบบใช้งานจริง", "condition": "ชุดใช้งานประจำวัน", "overall_style": "เครื่องแบบนักเรียนตามโลกของเรื่อง"}
    if funeral:
        return {"top": "เสื้อสุภาพเรียบง่ายสำหรับงานศพ", "bottom": "กางเกงขายาวหรือกระโปรงสุภาพ", "footwear": "รองเท้าสุภาพเรียบ", "outerwear": "", "accessories": "เครื่องประดับน้อยที่สุด", "colors": "ดำ เทาเข้ม หรือสีไว้ทุกข์ตามวัฒนธรรม", "materials": "ผ้าธรรมดาไม่มันวาว", "condition": "สะอาด สุภาพ", "overall_style": "ชุดไว้ทุกข์ที่ไม่แฟชั่นเกินโลกของเรื่อง"}
    if ritual:
        return {"top": "เสื้อสุภาพเรียบที่เหมาะกับบทบาทร่างทรง/ผู้ประกอบพิธีและยุคของเรื่อง", "bottom": "กางเกงขายาวหรือผ้าถุง/กระโปรงเรียบตามหลักฐานและวัฒนธรรม", "footwear": "รองเท้าหรือเท้าเปล่าตามพื้นที่ประกอบพิธีและหลักฐาน", "outerwear": "", "accessories": "เครื่องประกอบพิธีเฉพาะที่บทหรือ visual identity รองรับ", "colors": "สีเรียบ/หม่นที่เข้ากับบริบทพิธี ไม่แฟชั่นสุ่ม", "materials": "ผ้าธรรมดาหรือผ้าท้องถิ่นตามยุคและพื้นที่", "condition": "ใช้งานจริง", "overall_style": "ชุดที่เข้ากับบทบาทร่างทรงและบริบทพิธีของตัวละคร"}

    if thai and rural:
        top = "เสื้อยืดหรือเสื้อเชิ้ตผ้าฝ้ายเรียบ ใช้งานประจำวัน ไม่พิมพ์ลายแฟชั่นสมัยใหม่"
        bottom = "กางเกงขายาวผ้าฝ้าย/ผ้าทำงานทรงธรรมดา"
        footwear = "รองเท้าแตะหรือรองเท้าใช้งานเรียบง่าย"
        style = f"ชุดใช้งานจริงของตัวละครในบริบท {entity_place or 'ชุมชน/ครอบครัว'} ช่วง {era}"
    elif thai:
        top = "เสื้อท่อนบนเรียบง่ายตามวัย อาชีพ และฐานะ ไม่แฟชั่นเกินยุค"
        bottom = "กางเกงขายาวหรือกระโปรงทรงธรรมดาตามตัวละคร"
        footwear = "รองเท้าหรือรองเท้าแตะใช้งานประจำวันที่เหมาะกับกิจกรรมของตัวละคร"
        style = f"ชุดคนไทยใช้งานจริงช่วง {era} ตามบริบท {entity_place or region}"
    else:
        top = "เสื้อท่อนบนใช้งานประจำวันที่ตรงกับยุค วัฒนธรรม วัย อาชีพ และฐานะ"
        bottom = "กางเกงหรือกระโปรงใช้งานประจำวันที่ตรงกับตัวละคร"
        footwear = "รองเท้าใช้งานประจำวันที่ตรงกับกิจกรรม ยุค และฐานะ"
        style = f"ชุดธรรมดาที่มีความเป็นไปได้สูงใน {region} ช่วง {era} ตามบริบทของตัวละคร"
    if climate:
        style += f" และเหมาะกับอากาศ {climate}"
    return {"top": top, "bottom": bottom, "footwear": footwear, "outerwear": "", "accessories": "", "colors": "สีใช้งานจริงเป็นกลาง/หม่น สอดคล้องยุคและฐานะ", "materials": "วัสดุเสื้อผ้าที่หาได้จริงในยุคและพื้นที่", "condition": "สภาพใช้งานจริง สอดคล้องฐานะและกิจกรรม", "overall_style": style}


def _split_clothing_text(clothes, entity, story):
    """Split one explicit outfit sentence into non-duplicated garment fields."""
    base = _infer_default_outfit(entity, story)
    text = _text(clothes)
    if not text:
        return base
    clauses = [c.strip(" ,.;") for c in re.split(r"\s*(?:,|;|และ|กับ|พร้อม|\+)\s*", text) if c.strip(" ,.;")]
    assigned = {"top": [], "bottom": [], "footwear": [], "outerwear": [], "accessories": []}
    for clause in clauses:
        low = clause.casefold()
        if any(x in low for x in ("รองเท้า", "แตะ", "shoe", "sandal", "boot")):
            assigned["footwear"].append(clause)
        elif any(x in low for x in ("กางเกง", "กระโปรง", "ผ้าถุง", "pants", "trousers", "skirt", "sarong")):
            assigned["bottom"].append(clause)
        elif any(x in low for x in ("เสื้อคลุม", "แจ็กเก็ต", "แจ็คเก็ต", "jacket", "coat", "cardigan")):
            assigned["outerwear"].append(clause)
        elif any(x in low for x in ("หมวก", "แว่น", "นาฬิกา", "สร้อย", "เข็มขัด", "กระเป๋า", "accessor")):
            assigned["accessories"].append(clause)
        elif any(x in low for x in ("เสื้อ", "จีวร", "สูท", "shirt", "blouse", "t-shirt", "dress", "robe")):
            assigned["top"].append(clause)
    for key in assigned:
        if assigned[key]:
            base[key] = " และ ".join(assigned[key])
    colors = [term for term in _COLOR_TERMS if term in text]
    materials = [term for term in _MATERIAL_TERMS if term in text]
    if colors:
        base["colors"] = ", ".join(dict.fromkeys(colors))
    if materials:
        base["materials"] = ", ".join(dict.fromkeys(materials))
    base["overall_style"] = "ชุดตามรายละเอียดที่บทระบุ โดยรักษาชิ้นเสื้อผ้า สี วัสดุ และสภาพเดิม"
    return base


def normalize_character_wardrobe(entity, story=None):
    """Return normalized wardrobe dict, or None when this entity should not wear human clothing."""
    entity = entity if isinstance(entity, dict) else {}
    story = story if isinstance(story, dict) else {}
    kind = _entity_type(entity)
    explicit = _explicit_clothes(entity)
    if kind == "animal":
        return None
    if kind == "supernatural" and not (_is_humanoid_supernatural(entity) and explicit):
        return None

    existing = entity.get("wardrobe") if isinstance(entity.get("wardrobe"), dict) else {}
    existing_default = existing.get("default_outfit") if isinstance(existing.get("default_outfit"), dict) else {}
    # Migrate legacy aliases once; nested wardrobe becomes the canonical source of truth.
    source = _text(existing.get("wardrobe_source") or entity.get("wardrobe_source")).lower()
    if source not in ("explicit", "inferred"):
        source = "explicit" if explicit else "inferred"
    default = _split_clothing_text(explicit, entity, story) if explicit else _infer_default_outfit(entity, story)
    for key in tuple(default):
        if _known(existing_default.get(key)):
            default[key] = _text(existing_default.get(key))
    variants = existing.get("variants") if isinstance(existing.get("variants"), list) else []
    if not variants and isinstance(entity.get("outfit_variants"), list):
        variants = entity.get("outfit_variants")
    reason = _text(existing.get("wardrobe_reason") or entity.get("wardrobe_reason"))
    if not reason:
        reason = "ใช้เสื้อผ้าที่บทระบุจริงและแยกเป็นชิ้นสำหรับภาพเต็มตัว" if source == "explicit" else "อนุมานชุดธรรมดาที่มีความเป็นไปได้สูงที่สุดจากบริบทเฉพาะของตัวละคร"
        context = _inference_context(entity, story)
        if context:
            reason += ": " + context[:320]
    return {"default_outfit": default, "wardrobe_source": source, "wardrobe_reason": reason, "variants": variants}


def apply_character_wardrobe(entity, story=None):
    """Mutate one entity safely; nested wardrobe is the source of truth."""
    if not isinstance(entity, dict):
        return entity
    wardrobe = normalize_character_wardrobe(entity, story)
    if wardrobe is None:
        entity.pop("wardrobe", None)
        # Only preserve legacy aliases if they already existed; never invent them.
        if "wardrobe_source" in entity:
            entity["wardrobe_source"] = ""
        if "wardrobe_reason" in entity:
            entity["wardrobe_reason"] = ""
        return entity
    entity["wardrobe"] = wardrobe
    # Compatibility aliases are updated only when an old consumer already created them.
    if "wardrobe_source" in entity:
        entity["wardrobe_source"] = wardrobe["wardrobe_source"]
    if "wardrobe_reason" in entity:
        entity["wardrobe_reason"] = wardrobe["wardrobe_reason"]
    if not _known(entity.get("เสื้อผ้า")):
        entity["เสื้อผ้า"] = wardrobe["default_outfit"].get("overall_style") or "ชุดตามบริบทเรื่อง"
        if wardrobe["wardrobe_source"] == "inferred" and _INFER_MARK not in entity["เสื้อผ้า"]:
            entity["เสื้อผ้า"] += " " + _INFER_MARK
    return entity


def wardrobe_prompt_text(entity, story=None):
    """One immutable normalized outfit description for Front / 3/4 / Full-body Ref views."""
    wardrobe = normalize_character_wardrobe(entity, story)
    if not wardrobe:
        return "WARDROBE: none. ห้ามเพิ่มเสื้อ กางเกง/กระโปรง รองเท้า หรือ accessories แบบมนุษย์เอง"
    outfit = wardrobe["default_outfit"]
    order = (("top", "เสื้อ"), ("bottom", "กางเกง/กระโปรง/ผ้าถุง"), ("footwear", "รองเท้า"), ("outerwear", "เสื้อคลุม"), ("accessories", "accessories"), ("colors", "สี"), ("materials", "วัสดุ"), ("condition", "สภาพ"), ("overall_style", "ภาพรวม"))
    body = "; ".join(f"{label}: {_text(outfit.get(key))}" for key, label in order if _known(outfit.get(key)))
    return body + f". source={wardrobe['wardrobe_source']}. เหตุผล: {wardrobe['wardrobe_reason']}. WARDROBE LOCK: ใช้ default_outfit ก้อนนี้ชุดเดียวเหมือนกัน 100% ใน Front view, 3/4 view และ Full-body view; Full-body ต้องเห็นเสื้อ กางเกง/กระโปรง/ผ้าถุง รองเท้า และ accessories ที่ระบุครบ; ห้ามเปลี่ยนชุด สี วัสดุ รองเท้า หรือ accessories ระหว่างมุม."
