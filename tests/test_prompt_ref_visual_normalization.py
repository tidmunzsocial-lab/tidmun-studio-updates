# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "snapgen_modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from snapgen_prompt_ref_visual_normalization import (
    install_prompt_ref_visual_normalization,
    merge_preserve_nonempty,
    normalize_breakdown_aliases,
    normalize_character_aliases,
)


class PromptRefVisualNormalizationTests(unittest.TestCase):
    def test_eye_alias_fills_empty_canonical(self):
        item = normalize_character_aliases({"ดวงต": "ดวงตาสีน้ำตาล", "ดวงตา": ""})
        self.assertEqual(item["ดวงตา"], "ดวงตาสีน้ำตาล")
        self.assertNotIn("ดวงต", item)

    def test_clothing_alias_fills_empty_canonical(self):
        item = normalize_character_aliases({"เสื้อผ": "เสื้อยืดสีซีด", "เสื้อผ้า": ""})
        self.assertEqual(item["เสื้อผ้า"], "เสื้อยืดสีซีด")
        self.assertNotIn("เสื้อผ", item)

    def test_nonempty_canonical_wins_over_alias(self):
        item = normalize_character_aliases({"ดวงต": "ตาสีฟ้า", "ดวงตา": "ดวงตาสีน้ำตาล"})
        self.assertEqual(item["ดวงตา"], "ดวงตาสีน้ำตาล")
        self.assertNotIn("ดวงต", item)

    def test_empty_repair_does_not_clear_existing_visual_data(self):
        existing = {"main_characters": [{"name": "กัน", "entity_type": "human", "ดวงตา": "น้ำตาล", "เสื้อผ้า": "เสื้อยืด"}]}
        repair = {"main_characters": [{"name": "กัน", "entity_type": "human", "ดวงตา": "", "เสื้อผ้า": ""}]}
        merged = merge_preserve_nonempty(existing, repair)
        row = merged["main_characters"][0]
        self.assertEqual(row["ดวงตา"], "น้ำตาล")
        self.assertEqual(row["เสื้อผ้า"], "เสื้อยืด")

    def test_normalized_output_has_no_typo_aliases(self):
        payload = {
            "main_characters": [{"name": "กัน", "ดวงต": "น้ำตาล", "ดวงตา": "", "เสื้อผ": "เสื้อยืด", "เสื้อผ้า": ""}],
            "supporting_characters": [], "animals": [], "supernatural_entities": [], "characters": [],
        }
        row = normalize_breakdown_aliases(payload)["main_characters"][0]
        self.assertNotIn("ดวงต", row)
        self.assertNotIn("เสื้อผ", row)
        self.assertEqual(row["ดวงตา"], "น้ำตาล")
        self.assertEqual(row["เสื้อผ้า"], "เสื้อยืด")

    def test_complete_needs_ref_human_after_alias_normalization_skips_visual_repair(self):
        complete = {
            "version": 4,
            "story": {"title": "ทดสอบ"},
            "main_characters": [{
                "name": "กัน", "entity_type": "human", "needs_ref": True,
                "อายุ": "18 ปี", "เพศ": "ชาย", "รูปร่าง": "สมส่วน", "ส่วนสูง": "170 ซม.",
                "สีผิว": "น้ำผึ้ง", "ทรงผม": "ผมดำสั้น", "ใบหน้า": "หน้ารูปไข่",
                "ดวงต": "ดวงตาสีน้ำตาล", "ดวงตา": "", "เสื้อผ": "เสื้อยืดและกางเกงขายาว", "เสื้อผ้า": "",
                "visual_identity": "ชายวัยรุ่นไทย รูปร่างสมส่วน ผมดำสั้น หน้ารูปไข่ ดวงตาน้ำตาล มีรายละเอียดภาพจำชัดเจนเพียงพอสำหรับ reference",
            }],
            "supporting_characters": [], "animals": [], "supernatural_entities": [],
            "locations": [{"name": "บ้าน"}], "props": [], "scene_map": [],
        }
        calls = []
        persisted = []

        def original_normalize(value):
            out = dict(value)
            out["characters"] = list(out.get("main_characters") or [])
            return out

        required = ("อายุ", "เพศ", "รูปร่าง", "ส่วนสูง", "สีผิว", "ทรงผม", "ใบหน้า", "ดวงตา", "เสื้อผ้า", "visual_identity")
        def original_validator(value):
            for row in value.get("main_characters") or []:
                if row.get("needs_ref") and any(not str(row.get(k) or "").strip() for k in required):
                    return True
            return False

        def chat(messages, require_history=True):
            calls.append(messages[0]["content"])
            return json.dumps(complete, ensure_ascii=False)

        g = {
            "_normalize_prompt_ref_breakdown": original_normalize,
            "_prompt_ref_visual_bible_incomplete": original_validator,
            "_parse_bridge_context_json": lambda raw: json.loads(raw),
            "_prompt_ref_chat": chat,
            "_persist_prompt_ref_breakdown": lambda value: persisted.append(value),
            "_prompt_ref_context_quality_rules": lambda: "RULES ",
            "_prompt_ref_context_schema_text": lambda: "SCHEMA ",
        }
        self.assertTrue(install_prompt_ref_visual_normalization(g))
        result = g["_audit_prompt_ref_context"](json.dumps(complete, ensure_ascii=False), "story")
        self.assertEqual(len(calls), 1)  # semantic audit only; no VISUAL BIBLE REPAIR turn
        self.assertNotIn("VISUAL BIBLE REPAIR REQUIRED", calls[0])
        row = result["main_characters"][0]
        self.assertEqual(row["ดวงตา"], "ดวงตาสีน้ำตาล")
        self.assertEqual(row["เสื้อผ้า"], "เสื้อยืดและกางเกงขายาว")
        self.assertNotIn("ดวงต", row)
        self.assertNotIn("เสื้อผ", row)
        self.assertTrue(persisted)


if __name__ == "__main__":
    unittest.main()
