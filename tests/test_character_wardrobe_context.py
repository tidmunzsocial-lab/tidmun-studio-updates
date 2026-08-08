# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "snapgen_modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from snapgen_character_visual_bible import canonicalize_character
from snapgen_character_wardrobe import apply_character_wardrobe, normalize_character_wardrobe, wardrobe_prompt_text


class CharacterWardrobeCompatibilityTests(unittest.TestCase):
    def test_canonical_wardrobe_is_preserved_verbatim(self):
        entity = {"name": "แม่", "entity_type": "human", "wardrobe": {"top": "เสื้ออยู่บ้าน", "bottom": "ผ้าถุง", "footwear": "รองเท้าแตะ", "source": "inferred", "reason": "AI ตัดสินจากบท"}}
        expected = dict(entity["wardrobe"])
        wardrobe = normalize_character_wardrobe(entity, {"main_location": "วัด"})
        for key, value in expected.items():
            self.assertEqual(wardrobe[key], value)
        self.assertNotIn("จีวร", json.dumps(wardrobe, ensure_ascii=False))

    def test_apply_character_wardrobe_is_semantic_noop(self):
        entity = {"name": "แม่", "entity_type": "human"}
        self.assertIs(apply_character_wardrobe(entity, {"summary": "มีพระอยู่ในเรื่อง"}), entity)
        self.assertNotIn("wardrobe", entity)

    def test_legacy_clothing_text_is_preserved_not_split_or_inferred(self):
        entity = {"name": "กัน", "เสื้อผ้า": "เสื้อยืด + กางเกงลำลอง + รองเท้าแตะ"}
        char = canonicalize_character(entity)
        self.assertEqual(char["wardrobe"]["overall_style"], entity["เสื้อผ้า"])
        self.assertEqual(char["wardrobe"]["top"], "")
        self.assertEqual(char["wardrobe"]["bottom"], "")
        self.assertEqual(char["wardrobe"]["footwear"], "")

    def test_animal_without_ai_wardrobe_stays_none(self):
        entity = {"name": "แมว", "entity_type": "animal", "visual_identity": "แมวขนสั้น"}
        self.assertIsNone(normalize_character_wardrobe(entity, {}))
        self.assertIn("none", wardrobe_prompt_text(entity, {}))

    def test_prompt_serializer_only_reads_existing_wardrobe(self):
        entity = {"name": "ร่างทรงพ่อแก่", "entity_type": "human", "wardrobe": {"top": "เสื้อพิธีขาว", "bottom": "กางเกงผ้าขาว", "footwear": "เท้าเปล่า", "source": "inferred", "reason": "AI จากบท"}}
        text = wardrobe_prompt_text(entity, {"main_location": "บ้าน"})
        self.assertIn("เสื้อพิธีขาว", text)
        self.assertIn("กางเกงผ้าขาว", text)
        self.assertNotIn("ชุดคนไทย", text)


if __name__ == "__main__":
    unittest.main()
