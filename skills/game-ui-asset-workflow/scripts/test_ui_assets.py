"""Run with Python 3.10+ and Pillow: python -m unittest discover -s scripts."""
import argparse
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

import ui_assets as ui


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="game-ui-skill-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in ("reference", "generated", "prompts"):
            (self.root / name).mkdir()
        background = Image.new("RGBA", (96, 64), (210, 209, 202, 255))
        panel = Image.new("RGBA", background.size)
        ImageDraw.Draw(panel).rounded_rectangle((14, 8, 63, 31), 3, fill=(35, 35, 38, 220))
        button = Image.new("RGBA", background.size)
        ImageDraw.Draw(button).rounded_rectangle((30, 26, 51, 39), 2, fill=(160, 24, 34, 235))
        self.layers = [background, panel, button]
        reference = background.copy()
        for layer in self.layers[1:]:
            reference = Image.alpha_composite(reference, layer)
        reference.save(self.root / "reference/mockup.png")
        self.plan = {"schema_version": 1, "reference": "reference/mockup.png", "canvas": [96, 64],
                     "rounds": [], "assets": [], "instances": []}
        for index, (name, box) in enumerate((("background", [0, 0, 96, 64]),
                                            ("panel", [12, 6, 54, 28]),
                                            ("button", [28, 24, 26, 18])), 1):
            rid = f"r0{index}"
            self.layers[index - 1].save(self.root / f"generated/{rid}.png")
            (self.root / f"prompts/{rid}.md").write_text(f"Synthetic fixture for {name}", encoding="utf-8")
            self.plan["rounds"].append({"id": rid, "image": f"generated/{rid}.png"})
            self.plan["assets"].append({"id": name, "kind": name, "required": True, "critical": True,
                                         "alpha": "opaque" if index == 1 else "transparent",
                                         "size": box[2:], "round": rid, "sheet_box": box, "file": f"assets/{name}.png"})
            self.plan["instances"].append({"id": f"{name}-main", "asset": name, "xy": box[:2], "z": index})
        self.save_plan()

    def save_plan(self):
        ui.write_json(self.root / "plan.json", self.plan)

    def extract_all(self):
        for rid in ("r01", "r02", "r03"):
            ui.extract(self.root, self.plan, argparse.Namespace(round=rid, normalize_size=False, replace=False))

    def baseline_review(self):
        self.extract_all()
        ui.compose(self.root, self.plan)
        comparison = ui.compare(self.root, self.plan, argparse.Namespace(actual="assembly/reconstructed.png"))
        score = {"score": 100, "notes": "Synthetic exact reconstruction fixture", "evidence": ["qa/overlay.png"]}
        review = {key: comparison[key] for key in ("reference_sha256", "actual_sha256", "state_sha256")}
        review.update({"scoring_policy": "visual-v2", "delivery_scope": "assets-preview", "criteria": {key: copy.deepcopy(score) for key in
                        ("layout", "appearance", "edges", "assembly")},
                       "critical_instances": [dict(copy.deepcopy(score), id=i["id"]) for i in self.plan["instances"]],
                       "issues": []})
        self.save_review(review)
        return review

    def save_review(self, review):
        ui.write_json(self.root / "qa/review.json", review)

    def test_three_rounds_reconstruct_overlapping_objects_exactly(self):
        ui.load_plan(self.root)
        for rid in ("r01", "r02", "r03"):
            result = ui.annotate(self.root, self.plan, argparse.Namespace(round=rid))
            self.assertEqual(ui.rgba(Path(result["annotation"])).size, (96, 64))
        self.baseline_review()
        expected = ui.rgba(self.root / self.plan["reference"])
        actual = ui.rgba(self.root / "assembly/reconstructed.png")
        self.assertIsNone(ImageChops.difference(expected, actual).convert("RGB").getbbox())
        self.assertEqual(ui.read_json(self.root / "qa/comparison.json")["mean_absolute_rgb_error"], 0)
        report = ui.verify(self.root, self.plan)
        self.assertTrue(report["passed"])
        self.assertEqual(report["completion_score"], 100)

    def test_same_round_overlap_is_rejected(self):
        self.plan["assets"][2]["round"] = "r02"
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "overlapping"):
            ui.load_plan(self.root)

    def test_wrong_sheet_ratio_is_rejected_even_with_normalization(self):
        self.layers[2].resize((100, 64)).save(self.root / "generated/r03.png")
        with self.assertRaisesRegex(ValueError, "dimensions"):
            ui.extract(self.root, self.plan, argparse.Namespace(round="r03", normalize_size=True, replace=False))

    def test_equal_ratio_normalization_is_explicit_and_keeps_raw_source(self):
        self.layers[2].resize((192, 128)).save(self.root / "generated/r03.png")
        with self.assertRaises(ValueError):
            ui.extract(self.root, self.plan, argparse.Namespace(round="r03", normalize_size=False, replace=False))
        ui.extract(self.root, self.plan, argparse.Namespace(round="r03", normalize_size=True, replace=False))
        self.assertEqual(ui.rgba(self.root / "generated/r03.png").size, (192, 128))
        self.assertEqual(ui.rgba(self.root / "assets/button.png").size, (26, 18))

    def test_fake_transparency_and_empty_crops_are_rejected(self):
        for color in ((255, 255, 255, 255), (0, 0, 0, 0)):
            Image.new("RGBA", (96, 64), color).save(self.root / "generated/r03.png")
            with self.assertRaises(ValueError):
                ui.extract(self.root, self.plan, argparse.Namespace(round="r03", normalize_size=False, replace=False))

    def test_high_aggregate_cannot_hide_a_bad_critical_button(self):
        review = self.baseline_review()
        review["critical_instances"][2]["score"] = 60
        self.save_review(review)
        result = ui.verify(self.root, self.plan)
        self.assertEqual(result["completion_score"], 100)
        self.assertFalse(result["passed"])
        self.assertTrue(any("button-main" in item for item in result["blockers"]))

    def test_open_major_issue_blocks_high_score(self):
        review = self.baseline_review()
        review["issues"] = [{"severity": "major", "status": "open", "detail": "Wrong character identity"}]
        self.save_review(review)
        self.assertFalse(ui.verify(self.root, self.plan)["passed"])

    def test_scores_below_ninety_fail(self):
        review = self.baseline_review()
        for criterion in review["criteria"].values():
            criterion["score"] = 80
        self.save_review(review)
        result = ui.verify(self.root, self.plan)
        self.assertEqual(result["completion_score"], 80)
        self.assertFalse(result["passed"])

    def test_changed_layout_invalidates_old_review(self):
        self.baseline_review()
        self.plan["instances"][2]["xy"][0] += 1
        self.save_plan()
        result = ui.verify(self.root, self.plan)
        self.assertFalse(result["passed"])
        self.assertTrue(any("state_sha256" in item for item in result["blockers"]))

    def test_missing_or_modified_asset_cannot_pass(self):
        self.baseline_review()
        (self.root / "assets/button.png").unlink()
        self.assertFalse(ui.verify(self.root, self.plan)["passed"])

    def test_static_reconstruction_is_not_runtime_implementation(self):
        review = self.baseline_review()
        review["delivery_scope"] = "game-implementation"
        review["runtime_evidence"] = {"scene": "main", "capture_source": "fixture", "interactions": ["start"]}
        self.save_review(review)
        self.assertFalse(ui.verify(self.root, self.plan)["passed"])

    def test_missing_review_cannot_pass(self):
        self.extract_all()
        ui.compose(self.root, self.plan)
        ui.compare(self.root, self.plan, argparse.Namespace(actual="assembly/reconstructed.png"))
        self.assertFalse(ui.verify(self.root, self.plan)["passed"])

    def test_command_line_signals_success_and_failed_delivery(self):
        self.baseline_review()
        command = [sys.executable, "-B", "-X", "utf8", ui.__file__, "verify", "--run", str(self.root)]
        success = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertTrue(json.loads(success.stdout)["passed"])
        (self.root / "assets/button.png").unlink()
        failure = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(failure.returncode, 2, failure.stderr)
        self.assertFalse(json.loads(failure.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
