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
    apply_character_repairs, canonicalize_context, context_missing_fields, find_character, has_value,
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
        self.assertIn("top=เสื้อแขนสั้นผ้าฝ้ายลายดอกเล็กสีชมพูอ่อน", prompt)
        self.assertIn("bottom=ผ้าถุงลายตารางสีน้ำเงินเข้มและแดงหม่น", prompt)
        self.assertIn("footwear=รองเท้าแตะพลาสติกสีน้ำเงิน", prompt)
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
        for collection in (broken["characters"], broken["supporting_characters"]):
            for char in collection:
                if char["character_id"] == "mother":
                    char["appearance"]["eyes"] = ""
        repair = {"repairs": [{"character_id": "mother", "appearance": {"eyes": "ตาสีน้ำตาล", "hair": "ผมสีทอง"}, "wardrobe": {"top": "จีวร"}}]}
        fixed = apply_character_repairs(broken, repair)
        mother2 = find_character(fixed, "mother")
        self.assertEqual(mother2["appearance"]["eyes"], "ตาสีน้ำตาล")
        self.assertEqual(mother2["appearance"]["hair"], "ผมดำรวบเรียบ")
        self.assertEqual(mother2["wardrobe"]["top"], "เสื้อแขนสั้นผ้าฝ้ายลายดอกเล็กสีชมพูอ่อน")

    def test_context_normalization_does_not_infer_semantic_wardrobe(self):
        legacy = {"story": {}, "characters": [{"name": "แม่", "entity_type": "human", "needs_ref": False}], "locations": [], "props": [], "scene_map": []}
        with tempfile.TemporaryDirectory() as tmp:
            normalized = normalize_context_master(tmp, data=legacy, invent=True)
        mother = find_character(normalized, "แม่")
        self.assertIsNone(mother["wardrobe"])
        self.assertFalse(mother["appearance"]["hair"])
        self.assertIsNone(normalize_character_wardrobe({"name": "แม่"}, {}))

    def test_complete_fixture_has_no_required_character_gaps(self):
        self.assertEqual(context_missing_fields(self.ctx), {})

    # ─── Cross-character differentiation tests ───────────────────────────────

    def test_kan_and_pee_chai_wardrobe_signature_differ(self):
        kan = find_character(self.ctx, "กัน")
        pee_chai = find_character(self.ctx, "พี่ชาย")
        self.assertIsNotNone(pee_chai, "fixture ต้องมี พี่ชาย")
        kan_ci = kan.get("costume_identity") or {}
        pee_ci = pee_chai.get("costume_identity") or {}
        self.assertNotEqual(
            kan_ci.get("signature_palette"), pee_ci.get("signature_palette"),
            "กัน และ พี่ชาย ห้ามมี signature_palette เหมือนกัน"
        )
        self.assertNotEqual(
            kan_ci.get("signature_silhouette"), pee_ci.get("signature_silhouette"),
            "กัน และ พี่ชาย ห้ามมี silhouette เหมือนกัน"
        )

    def test_mother_palette_differs_from_male_characters(self):
        mother = find_character(self.ctx, "แม่")
        mother_palette = set((mother.get("costume_identity") or {}).get("signature_palette") or [])
        self.assertTrue(mother_palette, "แม่ ต้องมี signature_palette")
        for name in ["กัน", "ลุงเทือง", "ร่างทรงพ่อแก่"]:
            char = find_character(self.ctx, name)
            other_palette = set((char.get("costume_identity") or {}).get("signature_palette") or [])
            self.assertFalse(
                mother_palette == other_palette,
                f"แม่ ห้ามมี signature_palette เหมือนกับ {name}"
            )

    def test_uncle_thueang_costume_reflects_deacon_role(self):
        uncle = find_character(self.ctx, "uncle-thueang")
        ci = uncle.get("costume_identity") or {}
        wardrobe = uncle.get("wardrobe") or {}
        ci_blob = json.dumps(ci, ensure_ascii=False)
        wardrobe_blob = json.dumps(wardrobe, ensure_ascii=False)
        self.assertTrue(
            any(kw in ci_blob + wardrobe_blob for kw in ["ขาว", "เชิ้ต", "สุภาพ", "มัคนายก", "วัด", "ชุมชน"]),
            "ลุงเทือง costume identity ต้องสะท้อนบทบาทมัคนายก"
        )
        medium = find_character(self.ctx, "ร่างทรงพ่อแก่")
        medium_ci = medium.get("costume_identity") or {}
        self.assertNotEqual(
            ci.get("signature_palette"), medium_ci.get("signature_palette"),
            "ลุงเทือง ห้ามมี signature_palette เหมือน ร่างทรง"
        )

    def test_medium_has_distinct_ritual_costume_identity(self):
        medium = find_character(self.ctx, "ร่างทรงพ่อแก่")
        ci = medium.get("costume_identity") or {}
        self.assertTrue(has_value(ci.get("signature_palette")), "ร่างทรง ต้องมี signature_palette")
        self.assertTrue(has_value(ci.get("recognition_cue")), "ร่างทรง ต้องมี recognition_cue")
        wardrobe_blob = json.dumps(medium.get("wardrobe"), ensure_ascii=False)
        ci_blob = json.dumps(ci, ensure_ascii=False)
        self.assertTrue(
            any(kw in wardrobe_blob + ci_blob for kw in ["พิธี", "สไบ", "ลูกประคำ", "แดง"]),
            "ร่างทรง ต้องมี ritual markers ในเสื้อผ้าหรือ costume_identity"
        )

    def test_no_two_human_characters_have_identical_signature_palette(self):
        human_chars = [c for c in self.ctx["characters"] if c.get("entity_type") == "human"]
        palettes = []
        for c in human_chars:
            ci = c.get("costume_identity")
            if isinstance(ci, dict) and has_value(ci.get("signature_palette")):
                palettes.append(tuple(sorted(ci["signature_palette"])))
        self.assertGreater(len(palettes), 1, "ต้องมี human characters ที่มี costume_identity อย่างน้อย 2 คน")
        self.assertEqual(len(palettes), len(set(palettes)), "ห้ามมี human characters ที่มี signature_palette เหมือนกัน")

    def test_no_generic_wardrobe_placeholders_in_human_canonical(self):
        BANNED = ["ตรงกับยุค", "เหมาะกับตัวละคร"]
        for c in self.ctx["characters"]:
            if c.get("entity_type") != "human":
                continue
            wardrobe = c.get("wardrobe") or {}
            for field in ("top", "bottom", "footwear"):
                val = str(wardrobe.get(field) or "")
                for phrase in BANNED:
                    self.assertNotIn(
                        phrase, val,
                        f"{c['character_id']}.wardrobe.{field} มี generic placeholder '{phrase}'"
                    )

    def test_reorder_does_not_change_costume_identity(self):
        before = {c["character_id"]: deepcopy(c.get("costume_identity")) for c in self.ctx["characters"]}
        reordered = deepcopy(self.raw)
        reordered["supporting_characters"] = list(reversed(reordered["supporting_characters"]))
        after_ctx = canonicalize_context(reordered)
        after = {c["character_id"]: c.get("costume_identity") for c in after_ctx["characters"]}
        self.assertEqual(before, after)

    def test_animal_has_no_wardrobe_and_no_costume_identity(self):
        cat = find_character(self.ctx, "แมว")
        self.assertEqual(cat["entity_type"], "animal")
        self.assertIsNone(cat["wardrobe"])
        self.assertIsNone(cat.get("costume_identity"))


if __name__ == "__main__":
    unittest.main()
