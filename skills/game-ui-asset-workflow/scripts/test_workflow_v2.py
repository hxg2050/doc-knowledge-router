"""Behavioral tests for registration, provenance, visual gates and delivery."""
import argparse
import json
import subprocess
import sys
import zipfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

import ui_assets as ui
from asset_delivery import inspect_images, pack, preview
from asset_processing import nine_slice, register, uniform_landmarks
import test_ui_assets as legacy


class WorkflowV2Tests(unittest.TestCase):
    save_plan = legacy.WorkflowTests.save_plan
    save_review = legacy.WorkflowTests.save_review
    extract_all = legacy.WorkflowTests.extract_all

    def setUp(self):
        legacy.WorkflowTests.setUp(self)
        self.plan["schema_version"] = 2
        self.plan["regions"] = []
        for asset, instance in zip(self.plan["assets"], self.plan["instances"]):
            asset["strategy"] = "generate"
            self.plan["regions"].append({"id": asset["id"], "box": instance["xy"] + asset["size"],
                                         "instances": [instance["id"]], "critical": True})
        self.save_plan()

    def baseline_review(self):
        self.extract_all()
        inspect_images(self.root, self.plan, argparse.Namespace(asset=None, image=None))
        ui.compose(self.root, self.plan)
        comparison = ui.compare(self.root, self.plan, argparse.Namespace(actual="assembly/reconstructed.png"))
        ui.review_template(self.root, self.plan, argparse.Namespace(replace=False))
        review = ui.read_json(self.root / "qa/review-draft.json")
        for entry in list(review["criteria"].values()) + review["regions"]:
            entry.update(score=100, notes="Viewed synthetic evidence: exact independent-layer reconstruction")
        review["checks"] = dict.fromkeys(review["checks"], True)
        self.save_review(review)
        self.assertTrue(ui.verify(self.root, self.plan)["passed"])
        return review

    def registration_recipe(self, kind="place"):
        round_info = self.plan["rounds"][2]
        raw = "generated/r03.png"
        round_info.update(raw_image=raw, image="generated/r03-registered.png", recipe="recipes/r03.json")
        recipe = {"operations": [{"asset": "button", "type": kind, "source": raw, "source_box": [28, 24, 26, 18]}]}
        ui.write_json(self.root / round_info["recipe"], recipe)
        self.save_plan()
        return round_info, recipe

    def test_near_canvas_size_registers_without_overwriting_raw(self):
        round_info, recipe = self.registration_recipe()
        raw = Image.new("RGBA", (97, 64)); raw.alpha_composite(self.layers[2]); raw.save(self.root / round_info["raw_image"])
        before = ui.sha(self.root / round_info["raw_image"])
        ui.load_plan(self.root)
        register(self.root, self.plan, argparse.Namespace(round="r03", replace=False))
        self.assertEqual(ui.rgba(self.root / round_info["image"]).size, (96, 64))
        self.assertEqual(ui.sha(self.root / round_info["raw_image"]), before)
        self.baseline_review()
        self.assertTrue(ui.status(self.root, self.plan, mode="strict")["review_current"])

    def test_uniform_landmarks_and_nonuniform_distortion(self):
        points = [{"source": [0, 0], "target": [12, 8]}, {"source": [10, 0], "target": [32, 8]},
                  {"source": [0, 10], "target": [12, 28]}]
        scale, offset, error = uniform_landmarks(points, 0.01)
        self.assertAlmostEqual(scale, 2); self.assertAlmostEqual(offset[0], 12); self.assertAlmostEqual(offset[1], 8); self.assertAlmostEqual(error, 0)
        points[2]["target"][1] = 40
        with self.assertRaisesRegex(ValueError, "uniform"):
            uniform_landmarks(points, 1)

    def test_nine_slice_keeps_corners_and_rejects_crushed_target(self):
        tile = Image.new("RGBA", (10, 10), "white")
        tile.paste("red", (0, 0, 2, 2)); tile.paste("blue", (8, 8, 10, 10))
        result = nine_slice(tile, [24, 18], [2, 2, 2, 2], 1)
        self.assertEqual(result.crop((0, 0, 2, 2)).tobytes(), tile.crop((0, 0, 2, 2)).tobytes())
        self.assertEqual(result.getpixel((23, 17)), (0, 0, 255, 255))
        with self.assertRaisesRegex(ValueError, "corners"):
            nine_slice(tile, [4, 4], [2, 2, 2, 2], 1)

    def test_character_cannot_be_stretched_by_nine_slice(self):
        round_info, recipe = self.registration_recipe("nine-slice")
        self.plan["assets"][2]["kind"] = "character"
        recipe["operations"][0]["borders"] = [4, 4, 4, 4]
        ui.write_json(self.root / round_info["recipe"], recipe)
        with self.assertRaisesRegex(ValueError, "never warp"):
            register(self.root, self.plan, argparse.Namespace(round="r03", replace=False))

    def inpaint_background(self):
        r = self.plan["rounds"][0]
        r.update(raw_image=r["image"], image="generated/r01-registered.png", recipe="recipes/r01.json")
        (self.root / "masks").mkdir()
        mask = Image.new("L", (96, 64)); ImageDraw.Draw(mask).rectangle((12, 6, 66, 42), fill=255)
        mask.save(self.root / "masks/background.png")
        ui.write_json(self.root / r["recipe"], {"operations": [{"asset": "background", "type": "inpaint",
            "source": r["raw_image"], "base": "reference/mockup.png", "mask": "masks/background.png"}]})
        self.save_plan()
        register(self.root, self.plan, argparse.Namespace(round="r01", replace=False))
        return r

    def test_inpaint_preserves_visible_base_exactly(self):
        r = self.inpaint_background()
        actual = ui.rgba(self.root / r["image"])
        self.assertEqual(actual.tobytes(), self.layers[0].tobytes())
        self.assertEqual(actual.getpixel((0, 0)), ui.rgba(self.root / "reference/mockup.png").getpixel((0, 0)))
        record = ui.read_json(self.root / "provenance/registration.json")["r01"]
        self.assertIn("masks/background.png", record["inputs"])

    def test_raw_recipe_prompt_changes_invalidate_only_affected_round(self):
        r, recipe = self.registration_recipe()
        register(self.root, self.plan, argparse.Namespace(round="r03", replace=False))
        self.baseline_review()
        for name in (r["raw_image"], r["recipe"], "prompts/r03.md"):
            path = self.root / name; previous = path.read_bytes()
            with self.subTest(name=name):
                if path.suffix == ".png":
                    changed = ui.rgba(path); changed.putpixel((32, 28), (250, 0, 0, 255)); changed.save(path)
                else:
                    path.write_bytes(previous + b"\n ")
                result = ui.status(self.root, self.plan, mode="strict")
                self.assertFalse(result["review_current"]); self.assertIsNone(result["visual_score"])
                self.assertEqual(result["affected_assets"], ["button"])
                path.write_bytes(previous)
        self.assertTrue(ui.status(self.root, self.plan, mode="strict")["review_current"])

    def test_mask_change_invalidates_registration(self):
        self.inpaint_background(); self.baseline_review()
        path = self.root / "masks/background.png"
        mask = Image.open(path); mask.putpixel((0, 0), 255); mask.save(path); mask.close()
        self.assertEqual(ui.status(self.root, self.plan, mode="strict")["affected_assets"], ["background"])

    def test_crop_uses_actual_source_bounds_and_records_source(self):
        asset = self.plan["assets"][2]
        asset.update(round=None, strategy="crop", source={"file": "generated/r03.png", "box": [28, 24, 26, 18]},
                     source_note="Synthetic isolated complete button; no occlusion or background to remove")
        self.save_plan(); ui.load_plan(self.root)
        ui.extract(self.root, self.plan, argparse.Namespace(asset="button", replace=False))
        self.assertIn("generated/r03.png", ui.read_json(self.root / "provenance/extraction.json")["button"]["inputs"])
        asset["source"]["box"] = [95, 60, 26, 18]
        with self.assertRaisesRegex(ValueError, "outside"):
            ui.extract(self.root, self.plan, argparse.Namespace(asset="button", replace=True))

    def test_local_strategy_is_only_for_simple_layers(self):
        self.plan["assets"][2].update(round=None, strategy="local", source_note="Wrongly claimed character painted by script")
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "text/simple geometry"):
            ui.load_plan(self.root)

    def test_alpha_ghosts_and_near_opaque_rectangle_are_rejected(self):
        asset = self.plan["assets"][2]
        for alpha in (0, 1, 254, 255):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                ui.check_image(Image.new("RGBA", tuple(asset["size"]), (255, 255, 255, alpha)), asset, True)
        image = Image.new("RGBA", tuple(asset["size"])); ImageDraw.Draw(image).line((0, 4, 20, 4), fill=(10, 10, 10, 40))
        self.assertTrue(ui.check_image(image, asset, True)["warnings"])
        self.assertEqual(ui.check_image(image, asset, True)["visible_pixels"], 21)
        overlay = dict(asset, alpha="translucent")
        ui.check_image(Image.new("RGBA", tuple(asset["size"]), (0, 0, 0, 120)), overlay, True)

    def test_complete_region_must_exist_and_critical_score_cannot_be_averaged_away(self):
        self.plan["regions"].pop(); self.save_plan()
        ui.load_plan(self.root)  # Production may proceed without full review coverage.
        result = ui.verify(self.root, self.plan)
        self.assertFalse(result["passed"])
        self.assertTrue(any("review region" in b for b in result["blockers"]))
        self.plan["regions"].append({"id": "button", "box": [28, 24, 26, 18], "instances": ["button-main"], "critical": True})
        self.save_plan(); review = self.baseline_review()
        review["regions"][2]["score"] = 65; self.save_review(review)
        result = ui.verify(self.root, self.plan)
        self.assertEqual(result["visual_score"], 100); self.assertFalse(result["passed"])

    def test_coverage_does_not_boost_visual_score_or_override_appearance(self):
        review = self.baseline_review()
        for entry in review["criteria"].values(): entry["score"] = 80
        self.save_review(review); result = ui.verify(self.root, self.plan)
        self.assertEqual(result["coverage"], 100); self.assertEqual(result["visual_score"], 80)
        for entry in review["criteria"].values(): entry["score"] = 100
        review["criteria"]["appearance"]["score"] = 89; self.save_review(review)
        result = ui.verify(self.root, self.plan)
        self.assertGreaterEqual(result["visual_score"], 90); self.assertFalse(result["passed"])

    def test_unchecked_alpha_stale_evidence_and_changed_review_cannot_pass(self):
        review = self.baseline_review()
        review["checks"]["alpha_on_light_and_dark"] = False; self.save_review(review)
        self.assertFalse(ui.status(self.root, self.plan, mode="strict")["review_current"])
        review["checks"]["alpha_on_light_and_dark"] = True; self.save_review(review)
        Image.new("RGB", (10, 10), "red").save(self.root / "qa/alpha/button.png")
        self.assertFalse(ui.verify(self.root, self.plan)["passed"])

    def test_blank_review_template_and_legacy_policy_never_auto_pass(self):
        review = self.baseline_review()
        draft = ui.read_json(self.root / "qa/review-draft.json"); self.save_review(draft)
        self.assertFalse(ui.verify(self.root, self.plan)["passed"])
        review.pop("scoring_policy"); self.save_review(review)
        self.assertFalse(ui.verify(self.root, self.plan)["passed"])

    def test_fractional_visual_score_is_not_false_precision(self):
        review = self.baseline_review(); review["criteria"]["layout"]["score"] = 99.5; self.save_review(review)
        self.assertFalse(ui.verify(self.root, self.plan)["passed"])

    def test_preview_handles_missing_assets_and_never_shows_stale_score(self):
        self.baseline_review(); (self.root / "assets/button.png").unlink()
        result = preview(self.root, self.plan, argparse.Namespace(replace=False), ui.status(self.root, self.plan, mode="strict"))
        data = ui.read_json(self.root / "preview/data.json")
        self.assertEqual(result["phase"], "assets-needed"); self.assertIsNone(data["state"]["visual_score"])
        self.assertIsNone(data["assets"][2]["url"])
        self.assertTrue((self.root / "preview/app.js").is_file())

    def test_verified_pack_contains_active_sources_and_rejects_stale_inputs(self):
        self.registration_recipe(); register(self.root, self.plan, argparse.Namespace(round="r03", replace=False))
        self.baseline_review(); args = argparse.Namespace(output="delivery/assets.zip", replace=False)
        result = pack(self.root, self.plan, args, ui.verify(self.root, self.plan))
        self.assertEqual(result["asset_count"], 3)
        with zipfile.ZipFile(self.root / args.output) as archive:
            self.assertIsNone(archive.testzip())
            for name in ("assets/button.png", "generated/r03.png", "generated/r03-registered.png", "recipes/r03.json", "plan.json", "qa/acceptance.json"):
                self.assertIn(name, archive.namelist())
        (self.root / "prompts/r03.md").write_text("Changed after review", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "blocked"):
            pack(self.root, self.plan, argparse.Namespace(output="delivery/new.zip", replace=False), ui.verify(self.root, self.plan))

    def test_stale_preview_must_be_refreshed_before_pack(self):
        preview(self.root, self.plan, argparse.Namespace(replace=False), ui.status(self.root, self.plan, mode="strict"))
        self.baseline_review()
        args = argparse.Namespace(output="delivery/assets.zip", replace=False)
        with self.assertRaisesRegex(ValueError, "snapshot is stale"):
            pack(self.root, self.plan, args, ui.verify(self.root, self.plan))
        preview(self.root, self.plan, argparse.Namespace(replace=True), ui.status(self.root, self.plan, mode="strict"))
        self.assertEqual(pack(self.root, self.plan, args, ui.verify(self.root, self.plan))["asset_count"], 3)

    def test_v2_requires_saved_standard_canvas_before_extracting(self):
        self.layers[2].resize((192, 128)).save(self.root / "generated/r03.png")
        with self.assertRaisesRegex(ValueError, "registered sheet"):
            ui.extract(self.root, self.plan, argparse.Namespace(round="r03", normalize_size=True, replace=False))

    def test_region_cannot_claim_a_whole_button_but_show_only_its_corner(self):
        self.plan["regions"][2]["box"] = [30, 26, 1, 1]; self.save_plan()
        with self.assertRaisesRegex(ValueError, "complete instance"):
            ui.load_plan(self.root)

    def test_full_command_line_workflow(self):
        self.registration_recipe()
        def run(command, *arguments):
            result = subprocess.run([sys.executable, "-B", "-X", "utf8", ui.__file__, command,
                                     "--run", str(self.root), *arguments], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            return json.loads(result.stdout)
        run("annotate", "--all"); run("register", "--round", "r03")
        for rid in ("r01", "r02", "r03"): run("extract", "--round", rid)
        run("audit"); run("inspect"); run("compose"); run("compare"); run("review-template")
        run("preview")
        review = ui.read_json(self.root / "qa/review-draft.json")
        for entry in list(review["criteria"].values()) + review["regions"]:
            entry.update(score=100, notes="Synthetic fixture viewed in integration test")
        review["checks"] = dict.fromkeys(review["checks"], True); self.save_review(review)
        self.assertTrue(run("verify")["passed"])
        self.assertTrue(run("status", "--mode", "strict")["review_current"])
        run("preview", "--mode", "strict", "--replace")
        self.assertEqual(run("pack")["asset_count"], 3)

    def test_optional_unused_asset_does_not_block_delivery(self):
        self.plan["assets"].append({"id": "unused", "kind": "icon", "strategy": "crop", "required": False,
                                    "alpha": "transparent", "size": [4, 4], "round": None, "file": "assets/unused.png",
                                    "source": {"file": "reference/unselected.png", "box": [0, 0, 4, 4]},
                                    "source_note": "Optional candidate outside the selected design"})
        self.save_plan(); ui.load_plan(self.root); self.baseline_review()
        args = argparse.Namespace(output="delivery/assets.zip", replace=False)
        self.assertEqual(pack(self.root, self.plan, args, ui.verify(self.root, self.plan))["asset_count"], 3)

    def test_unknown_crop_asset_reports_an_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown asset"):
            ui.extract(self.root, self.plan, argparse.Namespace(asset="missing", replace=False))

    def test_quick_preview_without_regions_never_runs_visual_review(self):
        self.plan.pop("regions"); self.save_plan()
        ui.load_plan(self.root)
        self.extract_all()
        with patch.object(ui, "_verify", side_effect=AssertionError("Quick mode ran strict review")), \
                patch.object(ui, "audit", wraps=ui.audit) as auditing:
            state = ui.status(self.root, self.plan)
            preview(self.root, self.plan, argparse.Namespace(replace=False), state)
            self.assertEqual(auditing.call_count, 1)
        self.assertTrue(state["structural_passed"])
        self.assertEqual(state["phase"], "assets-ready")
        self.assertEqual(state["strict_review"], "not-requested")
        self.assertIsNone(state["visual_score"])
        self.assertFalse((self.root / "qa/acceptance.json").exists())
        self.assertFalse((self.root / "qa/review-draft.json").exists())
        result = subprocess.run([sys.executable, "-B", ui.__file__, "preview", "--run", str(self.root), "--replace"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "qa/acceptance.json").exists())
        with self.assertRaisesRegex(ValueError, "review region"):
            ui.review_template(self.root, self.plan, argparse.Namespace(replace=False))

    def test_quick_status_preserves_old_acceptance_but_does_not_claim_it(self):
        self.baseline_review()
        before = (self.root / "qa/acceptance.json").read_bytes()
        state = ui.status(self.root, self.plan)
        self.assertFalse(state["review_current"])
        self.assertEqual(state["strict_review"], "not-requested")
        self.assertIsNone(state["visual_score"])
        self.assertEqual((self.root / "qa/acceptance.json").read_bytes(), before)
        (self.root / "assets/button.png").unlink()
        self.assertEqual(ui.status(self.root, self.plan)["affected_assets"], ["button"])

    def test_strict_status_audits_once_and_cli_fails_on_missing_review(self):
        self.extract_all()
        with patch.object(ui, "audit", wraps=ui.audit) as auditing:
            state = ui.status(self.root, self.plan, mode="strict")
            self.assertEqual(auditing.call_count, 1)
        self.assertEqual(state["strict_review"], "failed")
        result = subprocess.run([sys.executable, "-B", ui.__file__, "status", "--run", str(self.root), "--mode", "strict"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_missing_regions_cannot_bypass_strict_gate_with_valid_hashes(self):
        review = self.baseline_review()
        self.plan.pop("regions"); self.save_plan()
        comparison = ui.compare(self.root, self.plan, argparse.Namespace(actual="assembly/reconstructed.png"))
        for key in ("state_sha256", "actual_sha256", "reference_sha256", "evidence_sha256"):
            review[key] = comparison[key]
        review["regions"] = []; self.save_review(review)
        result = ui.verify(self.root, self.plan)
        self.assertFalse(result["passed"])
        self.assertEqual(result["visual_score"], 100)
        self.assertTrue(any("review region" in b for b in result["blockers"]))

    def test_small_asset_registers_on_reference_sized_sheet_and_reconstructs_exactly(self):
        r, _ = self.registration_recipe()
        r["canvas"] = self.plan["canvas"].copy()
        self.save_plan(); ui.load_plan(self.root)
        annotation = ui.annotate(self.root, self.plan, argparse.Namespace(round="r03"))
        self.assertEqual(ui.rgba(ui.Path(annotation["annotation"])).size, (96, 64))
        register(self.root, self.plan, argparse.Namespace(round="r03", replace=False))
        self.assertEqual(ui.rgba(self.root / r["image"]).size, (96, 64))
        self.baseline_review()
        self.assertEqual(ui.rgba(self.root / "assembly/reconstructed.png").tobytes(),
                         ui.rgba(self.root / "reference/mockup.png").tobytes())
        self.assertEqual(ui.rgba(self.root / "assets/button.png").size, (26, 18))
        record = ui.read_json(self.root / "provenance/extraction.json")["button"]
        self.assertEqual(record["normalized_size"], [96, 64])

    def test_matching_sheet_needs_no_registration_and_preserves_raw_pixels(self):
        self.plan["rounds"][2]["canvas"] = self.plan["canvas"].copy()
        before = ui.sha(self.root / "generated/r03.png")
        self.save_plan(); ui.load_plan(self.root); self.extract_all()
        ui.compose(self.root, self.plan)
        self.assertEqual(ui.rgba(self.root / "assembly/reconstructed.png").tobytes(),
                         ui.rgba(self.root / "reference/mockup.png").tobytes())
        self.assertEqual(ui.sha(self.root / "generated/r03.png"), before)
        self.assertEqual(ui.rgba(self.root / "assets/button.png").size, (26, 18))

    def test_smaller_and_larger_round_canvases_fail_before_writing_outputs(self):
        r, _ = self.registration_recipe()
        for schema in (1, 2):
            self.plan["schema_version"] = schema
            for size in ([26, 18], [120, 100], [64, 96]):
                with self.subTest(schema=schema, size=size):
                    r["canvas"] = size; self.save_plan()
                    with self.assertRaisesRegex(ValueError, "canvas must match the reference resolution"):
                        ui.load_plan(self.root)
                    with self.assertRaisesRegex(ValueError, "canvas must match the reference resolution"):
                        ui.annotate(self.root, self.plan, argparse.Namespace(round="r03"))
                    with self.assertRaisesRegex(ValueError, "canvas must match the reference resolution"):
                        register(self.root, self.plan, argparse.Namespace(round="r03", replace=False))
        self.assertFalse((self.root / "annotations/r03.png").exists())
        self.assertFalse((self.root / r["image"]).exists())
        result = subprocess.run([sys.executable, "-B", ui.__file__, "extract", "--run", str(self.root), "--round", "r03"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("canvas must match the reference resolution", result.stderr)
        self.assertFalse((self.root / "assets/button.png").exists())

    def test_invalid_round_canvas_and_out_of_bounds_box_fail_before_processing(self):
        for size in ([0, 24], [32.5, 24], [20, 10]):
            with self.subTest(size=size):
                self.plan["rounds"][2]["canvas"] = size; self.save_plan()
                with self.assertRaisesRegex(ValueError, "canvas"):
                    ui.load_plan(self.root)
        self.plan["rounds"][2]["canvas"] = self.plan["canvas"].copy()
        self.plan["assets"][2]["sheet_box"] = [80, 50, 26, 18]
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "sheet_box"):
            ui.load_plan(self.root)


if __name__ == "__main__":
    unittest.main()
