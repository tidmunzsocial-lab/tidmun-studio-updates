# -*- coding: utf-8 -*-
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "snapgen_modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from snapgen_character_ref_request import character_prompt_text, save_debug_snapshot
from snapgen_character_visual_bible import (
    apply_character_repairs, canonicalize_context, context_missing_fields, find_character,
)
from snapgen_character_wardrobe import normalize_character_wardrobe
from snapgen_context_tools import normalize_context_master

FIXTURE = ROOT / "tests" / "fixtures" / "maew_phi_ai_visual_bible.json"


class CharacterVisualBibleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(FIXTURE.read_text(encoding="utf-8-sig"))
        cls.ctx = canonicalize_context(cls.raw)

    def test_canonical_schema_has_no_legacy_aliases(self):
        banned = {"ดวงต", "ดวงตา", "เสื้อผ", "เสื้อผ้า", "อายุ", "เพศ", "รูปร่าง", "ทรงผม", "ใบหน้า"}
        for char in self.ctx["characters"]:
            self.assertFalse(banned.intersection(char.keys()))
            self.assertIn("appearance", char)
            self.assertIn("character_id", char)

    def test_fixture_character_invariants(self):
        mother = find_character(self.ctx, "แม่")
        self.assertEqual(mother["entity_type"], "human")
        self.assertEqual(mother["appearance"]["gender"], "หญิง")
        mother_blob = json.dumps(mother["wardrobe"], ensure_ascii=False)
        self.assertNotIn("จีวร", mother_blob); self.assertNotIn("สบง", mother_blob)
        self.assertIn("อยู่บ้าน", mother["wardrobe"]["overall_style"])

        uncle = find_character(self.ctx, "uncle-thueang")
        self.assertEqual(uncle["occupation"], "มัคนายก")
        self.assertNotIn("ร่างทรง", json.dumps(uncle["wardrobe"], ensure_ascii=False))

        medium = find_character(self.ctx, "ร่างทรงพ่อแก่")
        self.assertEqual(medium["occupation"], "ร่างทรง")
        self.assertIn("พิธี", json.dumps(medium["wardrobe"], ensure_ascii=False))

        kan = find_character(self.ctx, "กัน")
        self.assertIn("เสื้อยืด", kan["wardrobe"]["top"])
        self.assertIn("กางเกงลำลอง", kan["wardrobe"]["bottom"])

        cat = find_character(self.ctx, "แมว")
        self.assertEqual(cat["entity_type"], "animal")
        self.assertIsNone(cat["wardrobe"])

    def test_reordering_character_arrays_never_swaps_wardrobe(self):
        before = {c["character_id"]: deepcopy(c["wardrobe"]) for c in self.ctx["characters"]}
        reordered = deepcopy(self.raw)
        reordered["supporting_characters"] = list(reversed(reordered["supporting_characters"]))
        reordered["main_characters"] = list(reversed(reordered["main_characters"]))
        after_ctx = canonicalize_context(reordered)
        after = {c["character_id"]: c["wardrobe"] for c in after_ctx["characters"]}
        self.assertEqual(before, after)

    def test_ref_prompt_serializes_exact_same_character_object(self):
        mother = find_character(self.ctx, "mother")
        prompt = character_prompt_text(mother)
        self.assertIn("character_id=mother", prompt)
        self.assertIn("top=เสื้อผ้าฝ้ายเรียบสำหรับอยู่บ้าน", prompt)
        self.assertIn("bottom=ผ้าถุงลายเรียบ", prompt)
        self.assertIn("footwear=รองเท้าแตะในบ้าน", prompt)
        self.assertIn("EXACTLY 3 visible depictions", prompt)
        self.assertIn("wardrobe object เดียวกัน 100%", prompt)
        self.assertNotIn("จีวร", prompt)

    def test_debug_snapshot_contains_exact_character_and_final_prompt(self):
        mother = find_character(self.ctx, "mother")
        prompt = character_prompt_text(mother)
        with tempfile.TemporaryDirectory() as tmp:
            path = save_debug_snapshot(tmp, mother, prompt)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["character_id"], "mother")
            self.assertEqual(payload["canonical_character"], mother)
            self.assertEqual(payload["final_ref_prompt"], prompt)
            self.assertTrue(payload["timestamp"])

    def test_repair_only_fills_missing_and_never_overwrites_existing(self):
        broken = deepcopy(self.ctx)
        mother = find_character(broken, "mother")
        # edit canonical copies in both flat and category by id to simulate missing source field
        for collection in (broken["characters"], broken["supporting_characters"]):
            for char in collection:
                if char["character_id"] == "mother":
                    char["appearance"]["eyes"] = ""
        repair = {"repairs": [{"character_id": "mother", "appearance": {"eyes": "ตาสีน้ำตาล", "hair": "ผมสีทอง"}, "wardrobe": {"top": "จีวร"}}]}
        fixed = apply_character_repairs(broken, repair)
        mother2 = find_character(fixed, "mother")
        self.assertEqual(mother2["appearance"]["eyes"], "ตาสีน้ำตาล")
        self.assertEqual(mother2["appearance"]["hair"], "ผมดำรวบเรียบ")
        self.assertEqual(mother2["wardrobe"]["top"], "เสื้อผ้าฝ้ายเรียบสำหรับอยู่บ้าน")

    def test_context_normalization_does_not_infer_semantic_wardrobe(self):
        legacy = {"story": {}, "characters": [{"name": "แม่", "entity_type": "human", "needs_ref": False}], "locations": [], "props": [], "scene_map": []}
        with tempfile.TemporaryDirectory() as tmp:
            normalized = normalize_context_master(tmp, data=legacy, invent=True)
        mother = find_character(normalized, "แม่")
        self.assertIsNone(mother["wardrobe"])
        self.assertFalse(mother["appearance"]["hair"])
        self.assertIsNone(normalize_character_wardrobe({"name": "แม่"}, {}))

    def test_complete_fixture_has_no_required_character_gaps(self):
        # Animal wardrobe is intentionally nullable. Humans must be complete.
        self.assertEqual(context_missing_fields(self.ctx), {})


if __name__ == "__main__":
    unittest.main()
