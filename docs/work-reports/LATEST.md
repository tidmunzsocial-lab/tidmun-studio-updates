# Latest Work Report

Current task: Wardrobe entity-aware normalization for Character Reference

Status: completed

Full work report:
- `docs/work-reports/2026-08-08_wardrobe-entity-aware-normalization.md`

Key handoff:
- Human explicit outfit strings are split into real top/bottom/footwear/etc fields.
- Animal entities do not receive human wardrobe.
- Supernatural entities receive wardrobe only when humanoid and explicit clothing is supported by story evidence.
- Nested `wardrobe` is canonical; legacy top-level source/reason aliases are only maintained when already present.
- Wardrobe inference uses character-owned context/role/evidence instead of blindly inheriting story main_location.
- Character Ref locks the same normalized outfit across Front / 3/4 / Full-body and explicitly requires visible top/bottom/footwear/accessories in full-body.
- New targeted wardrobe tests: 7/7 pass.
- Existing Prompt-Ref/Storyboard baseline remains 18 tests with 4 failures and 4 errors; no new regression.
- Unrelated working-tree changes remain and must not be staged blindly.
