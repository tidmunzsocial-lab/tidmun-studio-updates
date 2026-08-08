# -*- coding: utf-8 -*-
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "snapgen_modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from snapgen_character_visual_bible import canonicalize_context, context_missing_fields, find_character
from snapgen_prompt_ref_visual_normalization import install_prompt_ref_visual_normalization

FIXTURE = ROOT / "tests" / "fixtures" / "maew_phi_ai_visual_bible.json"


class PromptRefCanonicalVisualBibleTests(unittest.TestCase):
    def setUp(self):
        self.complete = json.loads(FIXTURE.read_text(encoding="utf-8-sig"))

    def _globals(self, chat):
        persisted = []
        g = {
            "_parse_bridge_context_json": lambda raw: json.loads(raw),
            "_prompt_ref_chat": chat,
            "_persist_prompt_ref_breakdown": lambda value: persisted.append(value),
        }
        return g, persisted

    def test_complete_ai_visual_bible_needs_no_semantic_audit_or_repair(self):
        calls = []
        g, persisted = self._globals(lambda messages, require_history=True: calls.append(messages) or "")
        self.assertTrue(install_prompt_ref_visual_normalization(g))
        result = g["_audit_prompt_ref_context"](json.dumps(self.complete, ensure_ascii=False), "story")
        self.assertEqual(calls, [])
        self.assertEqual(context_missing_fields(result), {})
        self.assertTrue(persisted)

    def test_schema_prompt_is_canonical_only(self):
        g, _ = self._globals(lambda messages, require_history=True: "")
        install_prompt_ref_visual_normalization(g)
        schema = g["_prompt_ref_context_schema_text"]()
        self.assertIn('"appearance"', schema)
        self.assertIn('"wardrobe"', schema)
        self.assertNotIn('"ดวงตา"', schema)
        self.assertNotIn('"เสื้อผ้า"', schema)

    def test_missing_field_repair_requests_only_missing_target(self):
        broken = deepcopy(self.complete)
        broken["supporting_characters"][0]["appearance"]["eyes"] = ""
        calls = []
        repair = {"repairs": [{"character_id": "mother", "appearance": {"eyes": "ตาสีน้ำตาล"}}]}
        def chat(messages, require_history=True):
            calls.append(messages[0]["content"])
            return json.dumps(repair, ensure_ascii=False)
        g, _ = self._globals(chat)
        install_prompt_ref_visual_normalization(g)
        fixed = g["_audit_prompt_ref_context"](json.dumps(broken, ensure_ascii=False), "story")
        self.assertEqual(len(calls), 1)
        self.assertIn("appearance.eyes", calls[0])
        self.assertIn("mother", calls[0])
        self.assertNotIn("VISUAL BIBLE REPAIR REQUIRED", calls[0])
        self.assertEqual(find_character(fixed, "mother")["appearance"]["eyes"], "ตาสีน้ำตาล")

    def test_repair_cannot_overwrite_existing_wardrobe(self):
        broken = deepcopy(self.complete)
        broken["supporting_characters"][0]["appearance"]["eyes"] = ""
        repair = {"repairs": [{"character_id": "mother", "appearance": {"eyes": "ตาน้ำตาล"}, "wardrobe": {"top": "จีวร"}}]}
        g, _ = self._globals(lambda messages, require_history=True: json.dumps(repair, ensure_ascii=False))
        install_prompt_ref_visual_normalization(g)
        fixed = g["_audit_prompt_ref_context"](json.dumps(broken, ensure_ascii=False), "story")
        mother = find_character(fixed, "mother")
        self.assertEqual(mother["wardrobe"]["top"], "เสื้อผ้าฝ้ายเรียบสำหรับอยู่บ้าน")
        self.assertNotIn("จีวร", json.dumps(mother, ensure_ascii=False))

    def test_needs_ref_false_does_not_require_visual_details(self):
        payload = {"story": {}, "characters": [{"name": "คนผ่านทาง", "character_id": "passer", "entity_type": "human", "needs_ref": False}], "locations": [], "props": [], "scene_map": []}
        canonical = canonicalize_context(payload)
        self.assertEqual(context_missing_fields(canonical), {})

    def test_legacy_aliases_are_removed_in_canonical_output(self):
        payload = {"story": {}, "characters": [{"name": "แม่", "needs_ref": False, "ดวงต": "น้ำตาล", "ดวงตา": "", "เสื้อผ": "ชุดเดิม", "เสื้อผ้า": ""}], "locations": [], "props": [], "scene_map": []}
        char = canonicalize_context(payload)["characters"][0]
        self.assertEqual(char["appearance"]["eyes"], "น้ำตาล")
        self.assertEqual(char["wardrobe"]["overall_style"], "ชุดเดิม")
        for alias in ("ดวงต", "ดวงตา", "เสื้อผ", "เสื้อผ้า"):
            self.assertNotIn(alias, char)


if __name__ == "__main__":
    unittest.main()
