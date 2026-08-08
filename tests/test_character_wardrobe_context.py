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
    def test_explicit_story_clothing_stays_explicit(self):
        story = {"era": "พ.ศ. 2540", "main_location": "ชนบทไทย"}
        character = {
            "name": "แดง",
            "เสื้อผ้า": "เสื้อเชิ้ตแขนสั้นสีซีด กางเกงขายาว และรองเท้าแตะ",
            "evidence": ["บทระบุว่าแดงใส่เสื้อเชิ้ตแขนสั้น กางเกงขายาว และรองเท้าแตะ"],
        }
        wardrobe = normalize_character_wardrobe(character, story)
        self.assertEqual(wardrobe["wardrobe_source"], "explicit")
        outfit = wardrobe["default_outfit"]
        self.assertIn("เสื้อเชิ้ต", outfit["top"])
        self.assertIn("กางเกง", outfit["bottom"])
        self.assertIn("รองเท้าแตะ", outfit["footwear"])

    def test_infers_plain_story_world_outfit(self):
        story = {
            "era": "พ.ศ. 2540",
            "country_or_region": "ชนบทภาคเหนือ ประเทศไทย",
            "main_location": "ไร่กระเทียม",
            "summary": "ครอบครัวเฝ้าไร่ในช่วงกลางคืนและใช้ชีวิตแบบชาวบ้าน",
        }
        character = {"name": "แบงค์", "อายุ": "วัยรุ่น", "เพศ": "ชาย", "ฐานะ": "ครอบครัวเกษตรกร"}
        wardrobe = normalize_character_wardrobe(character, story)
        self.assertEqual(wardrobe["wardrobe_source"], "inferred")
        outfit = wardrobe["default_outfit"]
        self.assertTrue(outfit["top"])
        self.assertTrue(outfit["bottom"])
        self.assertTrue(outfit["footwear"])
        self.assertIn("2540", outfit["overall_style"])
        self.assertNotIn("เกาหลี", outfit["overall_style"])

    def test_legacy_context_without_wardrobe_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {
                "story": {"era": "ยุคปัจจุบัน", "main_location": "กรุงเทพฯ"},
                "characters": [{"name": "เมย์", "อายุ": "25", "เพศ": "หญิง", "เสื้อผ้า": "ไม่ระบุ"}],
                "locations": [], "props": [], "scene_map": [],
            }
            normalized = normalize_context_master(tmp, data=data, invent=False)
            character = normalized["characters"][0]
            self.assertIn("wardrobe", character)
            self.assertIn("default_outfit", character["wardrobe"])
            self.assertEqual(character["wardrobe_source"], "inferred")

    def test_ref_prompt_text_contains_complete_wardrobe(self):
        story = {"era": "พ.ศ. 2540", "main_location": "ชนบทไทย"}
        character = {"name": "พ่อ", "อายุ": "45", "เพศ": "ชาย", "อาชีพ": "เกษตรกร", "ฐานะ": "รายได้ปานกลางค่อนต่ำ"}
        prompt = wardrobe_prompt_text(character, story)
        for token in ("เสื้อ:", "ท่อนล่าง:", "รองเท้า:", "สี:", "วัสดุ:", "สภาพ:", "ภาพรวม:"):
            self.assertIn(token, prompt)

    def test_front_three_quarter_full_body_share_one_outfit_lock(self):
        prompt = wardrobe_prompt_text({"name": "กัน"}, {"era": "ยุคปัจจุบัน", "main_location": "ประเทศไทย"})
        self.assertIn("Front view", prompt)
        self.assertIn("3/4 view", prompt)
        self.assertIn("Full-body view", prompt)
        self.assertIn("ชุดเดียวเหมือนกัน 100%", prompt)
        ref_source = (MODULES / "snapgen_page_ref.py").read_text(encoding="utf-8")
        self.assertIn("FULL-BODY ต้องเห็นเสื้อ ท่อนล่าง รองเท้า", ref_source)
        self.assertIn("WARDROBE:", ref_source)

    def test_inferred_clothing_is_not_reported_as_explicit_evidence(self):
        story = {"era": "พ.ศ. 2540", "main_location": "ชนบทไทย"}
        character = {
            "name": "น้อย",
            "เสื้อผ้า": "เสื้อผ้าเรียบง่าย (สมมุติเพื่อภาพ)",
            "evidence": ["บทระบุว่าน้อยอาศัยอยู่ในหมู่บ้าน"],
            "assumptions": ["สมมุติเสื้อผ้าให้เหมาะกับภาพ"],
        }
        wardrobe = normalize_character_wardrobe(character, story)
        self.assertEqual(wardrobe["wardrobe_source"], "inferred")
        self.assertNotIn("บทระบุ", wardrobe["wardrobe_reason"])


if __name__ == "__main__":
    unittest.main()
