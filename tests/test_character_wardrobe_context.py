# -*- coding: utf-8 -*-
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "snapgen_modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from snapgen_character_wardrobe import normalize_character_wardrobe, wardrobe_prompt_text
from snapgen_context_tools import normalize_context_master


class CharacterWardrobeContextTests(unittest.TestCase):
    def test_human_explicit_outfit_is_split_into_real_fields(self):
        story = {"era": "พ.ศ. 2540", "country_or_region": "ภาคเหนือ ประเทศไทย"}
        character = {
            "name": "แดง", "entity_type": "human",
            "เสื้อผ้า": "เสื้อเชิ้ตผ้าฝ้ายสีซีด, กางเกงขายาวสีน้ำตาล และรองเท้าแตะ",
            "evidence": ["บทระบุว่าแดงใส่เสื้อเชิ้ตผ้าฝ้ายสีซีด กางเกงขายาวสีน้ำตาล และรองเท้าแตะ"],
        }
        wardrobe = normalize_character_wardrobe(character, story)
        outfit = wardrobe["default_outfit"]
        self.assertEqual(wardrobe["wardrobe_source"], "explicit")
        self.assertIn("เสื้อเชิ้ต", outfit["top"])
        self.assertNotIn("กางเกง", outfit["top"])
        self.assertIn("กางเกง", outfit["bottom"])
        self.assertNotIn("รองเท้า", outfit["bottom"])
        self.assertIn("รองเท้าแตะ", outfit["footwear"])
        self.assertNotIn("เสื้อเชิ้ต", outfit["footwear"])
        self.assertIn("ผ้าฝ้าย", outfit["materials"])

    def test_animal_never_gets_default_human_clothing(self):
        animal = {"name": "เจ้าแมวส้ม", "entity_type": "animal", "visual_identity": "แมวส้มอ้วน"}
        self.assertIsNone(normalize_character_wardrobe(animal, {"country_or_region": "ประเทศไทย"}))
        with tempfile.TemporaryDirectory() as tmp:
            data = {"story": {"country_or_region": "ประเทศไทย"}, "characters": [animal], "locations": [], "props": [], "scene_map": []}
            normalized = normalize_context_master(tmp, data=data, invent=False)
            self.assertNotIn("wardrobe", normalized["characters"][0])

    def test_supernatural_is_not_given_human_clothing_automatically(self):
        ghost = {"name": "แสงผี", "entity_type": "supernatural_unknown", "visual_identity": "กลุ่มแสงสีเขียวลอยเหนือไร่"}
        self.assertIsNone(normalize_character_wardrobe(ghost, {"country_or_region": "ประเทศไทย"}))
        humanoid_without_explicit = {"name": "เงาคน", "entity_type": "supernatural_entity", "visual_identity": "เงาร่างคล้ายมนุษย์สูงผอม"}
        self.assertIsNone(normalize_character_wardrobe(humanoid_without_explicit, {}))

    def test_legacy_context_without_wardrobe_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {
                "story": {"era": "ยุคปัจจุบัน", "country_or_region": "ประเทศไทย"},
                "characters": [{"name": "เมย์", "อายุ": "25", "เพศ": "หญิง", "เสื้อผ้า": "ไม่ระบุ"}],
                "locations": [], "props": [], "scene_map": [],
            }
            character = normalize_context_master(tmp, data=data, invent=False)["characters"][0]
            self.assertIn("wardrobe", character)
            self.assertIn("default_outfit", character["wardrobe"])
            self.assertEqual(character["wardrobe"]["wardrobe_source"], "inferred")
            self.assertNotIn("wardrobe_source", character)  # nested wardrobe is source of truth

    def test_ref_prompt_uses_normalized_character_specific_wardrobe(self):
        story = {"era": "พ.ศ. 2540", "country_or_region": "ประเทศไทย", "main_location": "บ้านของกัน"}
        character = {"name": "ลุงเทือง", "entity_type": "human", "อายุ": "สูงวัย", "เพศ": "ชาย", "อาชีพ": "มัคนายก", "story_role": "มัคนายกประจำวัดในชุมชน", "evidence": ["ลุงเทืองเป็นมัคนายกของวัด"]}
        prompt = wardrobe_prompt_text(character, story)
        self.assertIn("เสื้อ:", prompt)
        self.assertIn("กางเกง/กระโปรง/ผ้าถุง:", prompt)
        self.assertIn("รองเท้า:", prompt)
        self.assertIn("บริบทสถานที่ของตัวละคร=วัด", prompt)
        self.assertNotIn("บ้านของกัน", prompt)
        ref_source = (MODULES / "snapgen_page_ref.py").read_text(encoding="utf-8")
        self.assertIn("wardrobe_prompt_text", ref_source)
        self.assertIn("WARDROBE:", ref_source)

    def test_front_three_quarter_full_body_share_same_outfit(self):
        character = {"name": "กัน", "entity_type": "human", "อายุ": "วัยรุ่น", "เพศ": "ชาย", "story_role": "ลูกในครอบครัว อยู่บ้านและช่วยงานครอบครัว"}
        prompt = wardrobe_prompt_text(character, {"era": "พ.ศ. 2540", "country_or_region": "ประเทศไทย"})
        self.assertIn("Front view", prompt)
        self.assertIn("3/4 view", prompt)
        self.assertIn("Full-body view", prompt)
        self.assertIn("ชุดเดียวเหมือนกัน 100%", prompt)
        self.assertIn("Full-body ต้องเห็นเสื้อ กางเกง/กระโปรง/ผ้าถุง รองเท้า", prompt)

    def test_humanoid_supernatural_needs_explicit_clothing_evidence(self):
        entity = {
            "name": "ผีหญิง", "entity_type": "supernatural_entity", "visual_identity": "ร่างหญิงคล้ายมนุษย์",
            "เสื้อผ้า": "เสื้อพื้นเมืองสีขาว และผ้าถุงสีดำ",
            "evidence": ["บทระบุว่าผีหญิงสวมเสื้อพื้นเมืองสีขาวและผ้าถุงสีดำ"],
        }
        wardrobe = normalize_character_wardrobe(entity, {"era": "อดีต", "country_or_region": "ภาคเหนือ ประเทศไทย"})
        self.assertIsNotNone(wardrobe)
        self.assertEqual(wardrobe["wardrobe_source"], "explicit")
        self.assertIn("เสื้อพื้นเมือง", wardrobe["default_outfit"]["top"])
        self.assertIn("ผ้าถุง", wardrobe["default_outfit"]["bottom"])


if __name__ == "__main__":
    unittest.main()
