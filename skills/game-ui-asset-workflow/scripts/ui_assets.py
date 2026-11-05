#!/usr/bin/env python3
"""Deterministic annotations, PNG crops, reconstruction and evidence gates.

Requires Python 3.10+ and Pillow 9.1+. Never generates artwork or calls a network API.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat
from asset_io import (archive_before_replace, crop_box, inside, ints, intersects,
                      local, read_json, rgba, sha, unique, write_json)
from asset_processing import register, registration_errors, sheet_canvas, snapshot, source_paths, strategy


def load_plan(root):
    plan = read_json(root / "plan.json")
    if plan.get("schema_version") not in (1, 2) or not ints(plan["canvas"], 2, True):
        raise ValueError("Expected schema_version 1 or 2 and a positive integer canvas")
    schema_v2 = plan["schema_version"] == 2
    for key in ("rounds", "assets", "instances"):
        unique(plan[key], key)
    if not plan["assets"] or not plan["instances"]:
        raise ValueError("An empty asset/instance list cannot establish coverage")
    width, height = plan["canvas"]
    with Image.open(local(root, plan["reference"])) as image:
        if image.size != (width, height):
            raise ValueError("Canvas does not match actual reference dimensions")
    rounds = {r["id"]: r for r in plan["rounds"]}
    for r in rounds.values():
        if not ints(sheet_canvas(plan, r), 2, True):
            raise ValueError(f"Invalid round canvas: {r['id']}")
        local(root, r["image"])
        for key in ("raw_image", "recipe"):
            if r.get(key):
                local(root, r[key])
        if schema_v2 and r.get("raw_image", r["image"]) != r["image"] and not r.get("recipe"):
            raise ValueError("Processed sheets need a declared recipe; do not silently relabel raw output")
    inputs = {local(root, plan["reference"])}
    for r in rounds.values():
        inputs.update(local(root, r[key]) for key in ("image", "raw_image", "recipe") if r.get(key))
    files = set()
    assets = {a["id"]: a for a in plan["assets"]}
    for asset in assets.values():
        if not ints(asset["size"], 2, True) or asset["alpha"] not in ("transparent", "opaque", "translucent"):
            raise ValueError(f"Invalid size or alpha: {asset['id']}")
        path = local(root, asset["file"])
        if path.suffix.lower() != ".png" or path in files or path in inputs:
            raise ValueError("Each asset needs a distinct PNG output path")
        files.add(path)
        if asset.get("critical") and not asset.get("required", True):
            raise ValueError(f"Critical asset cannot be optional: {asset['id']}")
        method = strategy(asset)
        if method not in ("generate", "remove-text", "complete-occlusion", "crop", "local"):
            raise ValueError(f"Unknown acquisition strategy: {asset['id']}")
        if schema_v2 and "strategy" not in asset:
            raise ValueError(f"Declare how each v2 asset is acquired: {asset['id']}")
        if not isinstance(asset.get("source_files", []), list):
            raise ValueError("source_files must contain run-relative file paths")
        for name in asset.get("source_files", []):
            local(root, name)
        for key in ("pivot", "padding"):
            if key in asset and not ints(asset[key], 2 if key == "pivot" else 4):
                raise ValueError(f"Invalid {key}: {asset['id']}")
        if schema_v2 and asset.get("kind") == "text":
            style = asset.get("text_style", {})
            if not asset.get("text") or not style.get("font") or type(style.get("size")) not in (int, float) or style["size"] <= 0 or type(style.get("baseline")) not in (int, float):
                raise ValueError("Text layers need text, font, size and baseline in text_style")
        if asset.get("round") is None:
            if method == "crop":
                source = asset["source"]
                if local(root, source["file"]) == path:
                    raise ValueError("Direct crop output cannot overwrite its source")
                if not ints(source["box"], 4) or source["box"][2:] != asset["size"] or not asset.get("source_note", "").strip():
                    raise ValueError("Direct crops need an exact source box and a note explaining why no repaint is needed")
            elif method != "local" or asset.get("kind") not in ("text", "geometry") or not asset.get("source_note", "").strip():
                raise ValueError("Only documented text/simple geometry can skip model provenance")
            continue
        if method in ("local", "crop"):
            raise ValueError("Local/crop assets cannot claim a generation round")
        box = asset["sheet_box"]
        if (asset["round"] not in rounds or not ints(box, 4) or box[2:] != asset["size"]
                or not inside(box, sheet_canvas(plan, rounds[asset["round"]]))):
            raise ValueError(f"Invalid sheet_box for round canvas: {asset['id']}")
    for r in rounds:
        group = [a for a in assets.values() if a.get("round") == r]
        for index, first in enumerate(group):
            for second in group[index + 1:]:
                if intersects(first["sheet_box"], second["sheet_box"]):
                    raise ValueError(f"Split overlapping assets into different rounds: {first['id']}, {second['id']}")
    for instance in plan["instances"]:
        if instance["asset"] not in assets or not ints(instance["xy"], 2) or type(instance["z"]) is not int:
            raise ValueError(f"Invalid instance: {instance['id']}")
        if not intersects(instance["xy"] + assets[instance["asset"]]["size"], [0, 0, width, height]):
            raise ValueError(f"Instance lies entirely outside canvas: {instance['id']}")
    regions = plan.get("regions", [])
    unique(regions, "regions")
    instance_ids = {i["id"] for i in plan["instances"]}
    for region in regions:
        if not inside(region["box"], plan["canvas"]) or not region.get("instances") or len(region["instances"]) != len(set(region["instances"])) or not set(region["instances"]) <= instance_ids:
            raise ValueError(f"Invalid visual region: {region['id']}")
        x, y, w, h = region["box"]
        for instance in (i for i in plan["instances"] if i["id"] in region["instances"]):
            ix, iy = instance["xy"]
            iw, ih = assets[instance["asset"]]["size"]
            if max(0, ix) < x or max(0, iy) < y or min(width, ix + iw) > x + w or min(height, iy + ih) > y + h:
                raise ValueError(f"Visual region must cover each declared complete instance: {region['id']}")
    return plan


def review_region_errors(plan):
    """Coverage is a strict review gate, not a prerequisite for asset production."""
    if plan["schema_version"] != 2:
        return []
    regions = plan.get("regions", [])
    covered = {key for r in regions for key in r["instances"]}
    critical_covered = {key for r in regions if r.get("critical") for key in r["instances"]}
    assets = {a["id"]: a for a in plan["assets"]}
    errors = []
    for instance in plan["instances"]:
        asset = assets[instance["asset"]]
        if asset.get("required", True) and instance["id"] not in covered:
            errors.append(f"Required instance needs a visual review region: {instance['id']}")
        if asset.get("critical") and instance["id"] not in critical_covered:
            errors.append(f"Critical instance needs a critical visual region: {instance['id']}")
    return errors


def check_image(image, asset, strict=False):
    if image.size != tuple(asset["size"]):
        raise ValueError(f"Wrong exported size: {asset['id']}")
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    threshold = asset.get("alpha_analysis", {}).get("visible_threshold", 16)
    if type(threshold) is not int or not 1 <= threshold <= 255:
        raise ValueError("visible_threshold must be an integer from 1 to 255")
    total = image.width * image.height
    visible = sum(histogram[threshold:])
    clear = sum(histogram[:3])
    if visible < min(4, total):
        raise ValueError(f"Empty or effectively invisible asset: {asset['id']}")
    if asset["alpha"] == "opaque" and histogram[255] != total:
        raise ValueError(f"Opaque asset contains alpha: {asset['id']}")
    if asset["alpha"] == "transparent":
        # v1 allowed semitransparent rectangular bars under this name.
        legacy_translucent = not strict and any(histogram[3:250])
        if clear < max(1, math.ceil(total * 0.005)) and not legacy_translucent:
            raise ValueError(f"No meaningful transparent area: {asset['id']}; use translucent for intentional overlays")
    if asset["alpha"] == "translucent" and not any(histogram[3:255]):
        raise ValueError(f"Translucent overlay needs actual partial alpha: {asset['id']}")
    bounds = alpha.point(lambda value: 255 if value >= threshold else 0).getbbox()
    touching = bool(bounds and (bounds[0] == 0 or bounds[1] == 0 or bounds[2] == image.width or bounds[3] == image.height))
    warnings = []
    if touching and asset["alpha"] == "transparent" and not asset.get("allow_edge_touch"):
        warnings.append("Visible content touches crop edge; inspect for unintended clipping")
    return {"visible_pixels": visible, "clear_ratio": clear / total, "visible_alpha_box": list(bounds) if bounds else None,
            "visible_threshold": threshold, "edge_touch": touching, "warnings": warnings}


def round_assets(plan, round_id):
    items = [a for a in plan["assets"] if a.get("round") == round_id]
    if not items:
        raise ValueError(f"No assets in round {round_id}")
    return items


def annotate(root, plan, args):
    image = rgba(local(root, plan["reference"]))
    if not getattr(args, "all", False):
        round_info = next((r for r in plan["rounds"] if r["id"] == args.round), None)
        if round_info is None:
            raise ValueError(f"Unknown round: {args.round}")
        # Explicit sheet coordinates need a neutral guide, not a misleading scene overlay.
        if "canvas" in round_info:
            image = Image.new("RGBA", tuple(sheet_canvas(plan, round_info)), "#f5f2e9")
    overlay = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", max(12, min(image.size) // 45))
    except OSError:
        font = ImageFont.load_default()
    if getattr(args, "all", False):
        assets = {a["id"]: a for a in plan["assets"]}
        boxes = [(i["id"], i["xy"] + assets[i["asset"]]["size"]) for i in plan["instances"]]
        name = "all"
    else:
        boxes = [(a["id"], a["sheet_box"]) for a in round_assets(plan, args.round)]
        name = args.round
    for asset_id, box in boxes:
        x, y, w, h = box
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill=(220, 32, 55, 25), outline=(220, 32, 55, 255), width=2)
        label = f"{asset_id} {w}x{h} @ {x},{y}"
        text_box = draw.textbbox((0, 0), label, font=font)
        tw, th = text_box[2] + 6, text_box[3] - text_box[1] + 6
        tx, ty = max(0, min(x, image.width - tw)), max(0, y - th)
        draw.rectangle((tx, ty, tx + tw, ty + th), fill=(0, 0, 0, 235))
        draw.text((tx + 3, ty + 3 - text_box[1]), label, fill="white", font=font)
    dest = root / "annotations" / f"{name}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(image, overlay).save(dest)
    return {"annotation": str(dest), "size": list(image.size)}


def extract(root, plan, args):
    crop_id = getattr(args, "asset", None)
    if crop_id:
        asset = next((a for a in plan["assets"] if a["id"] == crop_id), None)
        if asset is None:
            raise ValueError(f"Unknown asset: {crop_id}")
        if strategy(asset) != "crop":
            raise ValueError("--asset extraction is for declared direct crops; generated assets use --round")
        items = [asset]
        source = asset["source"]["file"]
    else:
        items = round_assets(plan, args.round)
        round_info = next(r for r in plan["rounds"] if r["id"] == args.round)
        errors = registration_errors(root, plan, round_info)
        if errors:
            raise ValueError("; ".join(errors))
        source = round_info["image"]
    source_path = local(root, source)
    image = rgba(source_path)
    original_size = list(image.size)
    target_size = original_size if crop_id else sheet_canvas(plan, round_info)
    width, height = target_size
    if not crop_id and image.size != (width, height):
        if plan["schema_version"] == 2:
            raise ValueError("v2 needs a saved registered sheet matching the round canvas; use register before extract")
        if not args.normalize_size or image.width * height != image.height * width:
            raise ValueError("Wrong sheet dimensions; only an explicitly reviewed equal-aspect normalization is allowed")
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    crops = []
    for asset in items:
        box = asset["source"]["box"] if crop_id else asset["sheet_box"]
        crop = crop_box(image, box)
        check_image(crop, asset, plan["schema_version"] == 2)
        dest = local(root, asset["file"])
        if dest.exists() and not args.replace:
            raise ValueError(f"Output exists; use a versioned filename or --replace: {dest}")
        crops.append((asset, crop, dest, box))
    manifest_path = root / "provenance/extraction.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    for asset, crop, dest, box in crops:
        if args.replace:
            archive_before_replace(root, dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        crop.save(dest)
        manifest[asset["id"]] = {
            "round": asset.get("round"), "source": source, "source_sha256": sha(source_path),
            "source_size": original_size, "normalized_size": target_size,
            "sheet_box": box, "file": asset["file"], "sha256": sha(dest),
            "inputs": snapshot(root, source_paths(root, plan, asset)),
        }
    if manifest_path.exists():
        archive_before_replace(root, manifest_path)
    write_json(manifest_path, manifest)
    return {"round": getattr(args, "round", None), "asset_count": len(crops), "normalized": not crop_id and original_size != target_size}


def audit(root, plan):
    provenance_path = root / "provenance/extraction.json"
    provenance = read_json(provenance_path) if provenance_path.exists() else {}
    used = {i["asset"] for i in plan["instances"]}
    results = []
    for asset in plan["assets"]:
        if not asset.get("required", True) and asset["id"] not in used:
            results.append({"id": asset["id"], "required": False, "passed": True, "skipped": True, "errors": []})
            continue
        errors, alpha_stats = [], None
        try:
            path = local(root, asset["file"])
            alpha_stats = check_image(rgba(path), asset, plan["schema_version"] == 2)
            snapshot(root, asset.get("source_files", []))
            if asset.get("required", True) and asset["id"] not in used:
                errors.append("Required asset has no assembled instance")
            if asset.get("round") is not None or strategy(asset) == "crop":
                record = provenance.get(asset["id"], {})
                if asset.get("round"):
                    round_info = next(r for r in plan["rounds"] if r["id"] == asset["round"])
                    source, box = round_info["image"], asset["sheet_box"]
                    if record.get("normalized_size") != sheet_canvas(plan, round_info):
                        errors.append("Missing or stale provenance: round canvas")
                    errors.extend(registration_errors(root, plan, round_info))
                    if not (root / "prompts" / f"{asset['round']}.md").is_file():
                        errors.append("Missing saved generation prompt")
                else:
                    source, box = asset["source"]["file"], asset["source"]["box"]
                expected = {"round": asset.get("round"), "source": source, "file": asset["file"],
                                   "sheet_box": box, "sha256": sha(path),
                                   "source_sha256": sha(local(root, source))}.items()
                for key, value in expected:
                    if record.get(key) != value:
                        errors.append(f"Missing or stale provenance: {key}")
                if plan["schema_version"] == 2 and record.get("inputs") != snapshot(root, source_paths(root, plan, asset)):
                    errors.append("Missing or stale provenance: input dependency chain")
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
        results.append({"id": asset["id"], "required": asset.get("required", True), "passed": not errors, "errors": errors,
                        "alpha": alpha_stats, "category": "text" if asset.get("kind") == "text" else "geometry" if asset.get("kind") == "geometry" else "art"})
    required = [r for r in results if r["required"]]
    coverage = 100 * sum(r["passed"] for r in required) / len(required) if required else 0
    counts = {category: sum(r.get("category") == category for r in results) for category in ("art", "text", "geometry")}
    result = {"structural_passed": bool(required) and all(r["passed"] for r in results), "coverage": coverage,
              "counts": counts, "instance_count": len(plan["instances"]), "assets": results}
    write_json(root / "qa/asset-audit.json", result)
    return result


def state_sha(root, plan):
    digest = hashlib.sha256((root / "plan.json").read_bytes())
    paths = {plan["reference"]}
    for asset in plan["assets"]:
        paths.add(asset["file"])
        paths.update(source_paths(root, plan, asset))
    for name in sorted(paths):
        path = local(root, name)
        digest.update(name.encode() + b"\0")
        digest.update((sha(path) if path.exists() else "MISSING").encode())
    return digest.hexdigest()


def compose(root, plan):
    if not audit(root, plan)["structural_passed"]:
        raise ValueError("Asset audit failed; inspect qa/asset-audit.json")
    image = Image.new("RGBA", tuple(plan["canvas"]))
    assets = {a["id"]: a for a in plan["assets"]}
    for instance in sorted(plan["instances"], key=lambda i: i["z"]):
        image.alpha_composite(rgba(local(root, assets[instance["asset"]]["file"])), tuple(instance["xy"]))
    dest = root / "assembly/reconstructed.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
    return {"assembled": str(dest), "size": list(image.size)}


def rgb_on_white(image):
    background = Image.new("RGBA", image.size, "white")
    return Image.alpha_composite(background, image).convert("RGB")


def compare(root, plan, args):
    reference_path = local(root, plan["reference"])
    actual_path = local(root, args.actual)
    reference, actual = rgba(reference_path), rgba(actual_path)
    if reference.size != actual.size:
        raise ValueError("Compare requires identical reference and actual dimensions")
    first, second = rgb_on_white(reference), rgb_on_white(actual)
    diff = ImageChops.difference(first, second)
    side = Image.new("RGB", (first.width * 2, first.height))
    side.paste(first, (0, 0))
    side.paste(second, (first.width, 0))
    qa = root / "qa"
    qa.mkdir(parents=True, exist_ok=True)
    side.save(qa / "side-by-side.png")
    Image.blend(first, second, 0.5).save(qa / "overlay.png")
    diff.point(lambda x: min(255, x * 4)).save(qa / "difference.png")
    evidence_paths = ["qa/side-by-side.png", "qa/overlay.png", "qa/difference.png", args.actual]
    metrics = {"reference": plan["reference"], "actual": args.actual, "canvas": plan["canvas"],
               "reference_sha256": sha(reference_path), "actual_sha256": sha(actual_path),
               "state_sha256": state_sha(root, plan),
               "mean_absolute_rgb_error": sum(ImageStat.Stat(diff).mean) / 3,
               "diagnostic_only": "Pixel error is not the visual review score", "regions": [], "instance_diagnostics": []}
    assets = {a["id"]: a for a in plan["assets"]}
    for instance in plan["instances"]:
        x, y = instance["xy"]
        w, h = assets[instance["asset"]]["size"]
        box = (max(0, x), max(0, y), min(first.width, x + w), min(first.height, y + h))
        metrics["instance_diagnostics"].append({"id": instance["id"], "box": list(box),
                                   "mean_absolute_rgb_error": sum(ImageStat.Stat(diff.crop(box)).mean) / 3})
    for region in plan.get("regions", []):
        x, y, w, h = region["box"]
        box = (x, y, x + w, y + h)
        side = Image.new("RGB", (w * 2, h))
        side.paste(first.crop(box), (0, 0))
        side.paste(second.crop(box), (w, 0))
        evidence = f"qa/region-{region['id']}.png"
        side.save(local(root, evidence))
        evidence_paths.append(evidence)
        metrics["regions"].append({"id": region["id"], "box": region["box"], "critical": region.get("critical", False),
                                   "evidence": evidence, "mean_absolute_rgb_error": sum(ImageStat.Stat(diff.crop(box)).mean) / 3})
    evidence_paths.extend(p.relative_to(root).as_posix() for p in sorted((qa / "alpha").glob("*.png")))
    metrics["evidence_sha256"] = snapshot(root, evidence_paths)
    write_json(qa / "comparison.json", metrics)
    return metrics


def review_score(root, entry, evidence_hashes=None, strict=False):
    value = entry.get("score")
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError("Review scores must be finite numbers between 0 and 100")
    if type(value) is not int:
        raise ValueError("Use integer visual review scores; avoid false precision")
    if not entry.get("notes", "").strip() or not entry.get("evidence"):
        raise ValueError("Every score needs review notes and image evidence")
    for evidence in entry["evidence"]:
        path = local(root, evidence)
        with Image.open(path) as image:
            image.verify()
        if strict and (evidence_hashes or {}).get(evidence) != sha(path):
            raise ValueError(f"Missing or stale visual evidence hash: {evidence}")
    return value


def verify(root, plan):
    return _verify(root, plan, audit(root, plan))


def _verify(root, plan, asset_audit):
    """Share a fresh audit within one command; never reuse an on-disk audit blindly."""
    report = {"passed": False, "visual_score": None, "completion_score": None,
              "scoring_policy": "visual-v2", "structural_passed": asset_audit["structural_passed"],
              "coverage": asset_audit["coverage"], "counts": asset_audit["counts"], "blockers": []}
    blockers = report["blockers"]
    blockers.extend(review_region_errors(plan))
    if not asset_audit["structural_passed"]:
        blockers.append("Asset audit failed; see qa/asset-audit.json")
    try:
        comparison = read_json(root / "qa/comparison.json")
        review = read_json(root / "qa/review.json")
        report["review_sha256"] = sha(root / "qa/review.json")
        current = {"reference_sha256": sha(local(root, plan["reference"])),
                   "actual_sha256": sha(local(root, comparison["actual"])), "state_sha256": state_sha(root, plan)}
        report.update(current)
        if review.get("scoring_policy") != "visual-v2":
            blockers.append("Legacy scoring policy; review again using visual-v2 (coverage earns no visual points)")
        if comparison.get("reference") != plan["reference"]:
            blockers.append("Reference path changed after comparison")
        for key, value in current.items():
            if comparison.get(key) != value or review.get(key) != value:
                blockers.append(f"Stale comparison or visual review: {key}")
        strict = plan["schema_version"] == 2
        evidence_hashes = review.get("evidence_sha256", {})
        if strict:
            if evidence_hashes != comparison.get("evidence_sha256"):
                blockers.append("Review evidence does not match the current comparison")
            for name, expected in comparison.get("evidence_sha256", {}).items():
                if sha(local(root, name)) != expected:
                    blockers.append(f"Stale comparison evidence: {name}")
            alpha_report = read_json(root / "qa/alpha-inspection.json")
            inspected = {r["id"]: r for r in alpha_report["images"]}
            active = {i["asset"] for i in plan["instances"]}
            for asset in plan["assets"]:
                if asset["id"] not in active or asset["alpha"] == "opaque":
                    continue
                record = inspected.get(asset["id"], {})
                if record.get("sha256") != sha(local(root, asset["file"])) or not evidence_hashes.get(record.get("evidence")):
                    blockers.append(f"Missing or stale light/dark alpha inspection: {asset['id']}")
        weights = {"layout": 0.35, "appearance": 0.45, "edges": 0.10, "assembly": 0.10}
        score = 0
        for name, weight in weights.items():
            score += review_score(root, review["criteria"][name], evidence_hashes, strict) * weight
        report["visual_score"] = report["completion_score"] = math.floor(score + 1e-9)
        if report["visual_score"] < 90:
            blockers.append("Visual score is below 90")
        if review["criteria"]["appearance"]["score"] < 90:
            blockers.append("Appearance must independently reach 90")
        if strict:
            checks = ("alpha_on_light_and_dark", "no_baked_checkerboard", "no_unintended_clipping", "background_without_extracted_objects")
            for name in checks:
                if review.get("checks", {}).get(name) is not True:
                    blockers.append(f"Visual check not reviewed: {name}")
            entries = review["regions"]
            unique(entries, "region review")
            entries = {e["id"]: e for e in entries}
            if set(entries) != {r["id"] for r in plan.get("regions", [])}:
                blockers.append("Visual review must cover exactly the current complete regions")
            for region in plan.get("regions", []):
                entry = entries.get(region["id"])
                if entry is None:
                    continue
                value = review_score(root, entry, evidence_hashes, True)
                if region.get("critical") and value < 90:
                    blockers.append(f"Critical region not accepted: {region['id']}")
        else:
            critical = {a["id"] for a in plan["assets"] if a.get("critical")}
            entries = review["critical_instances"]
            unique(entries, "critical review")
            entries = {e["id"]: e for e in entries}
            for instance in plan["instances"]:
                if instance["asset"] in critical:
                    entry = entries.get(instance["id"])
                    if entry is None or review_score(root, entry) < 90:
                        blockers.append(f"Critical instance not accepted: {instance['id']}")
        for issue in review["issues"]:
            if issue["severity"] not in ("critical", "major", "minor") or issue["status"] not in ("open", "resolved"):
                raise ValueError("Invalid issue severity or status")
            if issue["status"] == "open" and issue["severity"] in ("critical", "major"):
                blockers.append(f"Unresolved {issue['severity']}: {issue['detail']}")
        scope = review["delivery_scope"]
        if scope not in ("assets-preview", "game-implementation"):
            raise ValueError("Unknown delivery scope")
        if scope == "game-implementation":
            evidence = review.get("runtime_evidence", {})
            if (not evidence.get("scene") or not evidence.get("capture_source") or not evidence.get("interactions")
                    or comparison["actual"] == "assembly/reconstructed.png"):
                blockers.append("Game implementation needs a runtime capture and interaction evidence")
        report["delivery_scope"] = scope
    except (OSError, ValueError, KeyError, TypeError) as exc:
        blockers.append(f"Incomplete review evidence: {exc}")
    report["passed"] = not blockers
    report["assessment"] = "Visual scores are evidence-backed judgments, floored to whole points; structural checks are gates, not score bonuses"
    write_json(root / "qa/acceptance.json", report)
    return report


def status(root, plan, mode="quick"):
    if mode not in ("quick", "strict"):
        raise ValueError("Status mode must be quick or strict")
    result = audit(root, plan)
    current = state_sha(root, plan)
    result.update(mode=mode, state_sha256=current, review_current=False, strict_review="not-requested",
                  phase="assets-ready" if result["structural_passed"] else "assets-needed",
                  visual_score=None, blockers=[])
    result["affected_assets"] = [a["id"] for a in result["assets"] if not a["passed"]]
    if mode == "strict":
        review = _verify(root, plan, result)
        accepted = review["passed"]
        result.update(review_current=accepted, strict_review="passed" if accepted else "failed",
                      phase="accepted" if accepted else "review-needed" if result["structural_passed"] else "assets-needed",
                      visual_score=review.get("visual_score") if accepted else None, blockers=review["blockers"])
        result.update({key: review.get(key) for key in ("actual_sha256", "review_sha256")})
    return result


def review_template(root, plan, args):
    errors = review_region_errors(plan)
    if errors:
        raise ValueError("; ".join(errors))
    comparison = read_json(root / "qa/comparison.json")
    if comparison["state_sha256"] != state_sha(root, plan):
        raise ValueError("Run compare again after the last input change")
    dest = root / "qa/review-draft.json"
    if dest.exists() and not args.replace:
        raise ValueError("Review draft exists; preserve it or use --replace")
    empty = lambda evidence: {"score": None, "notes": "", "evidence": evidence}
    review = {key: comparison[key] for key in ("reference_sha256", "actual_sha256", "state_sha256", "evidence_sha256")}
    review.update(scoring_policy="visual-v2", delivery_scope="assets-preview",
                  criteria={name: empty(["qa/overlay.png" if name == "layout" else "qa/side-by-side.png"])
                            for name in ("layout", "appearance", "edges", "assembly")}, issues=[])
    if plan["schema_version"] == 2:
        review["regions"] = [dict(empty([r["evidence"]]), id=r["id"]) for r in comparison["regions"]]
        review["checks"] = {name: False for name in ("alpha_on_light_and_dark", "no_baked_checkerboard", "no_unintended_clipping", "background_without_extracted_objects")}
    else:
        assets = {a["id"]: a for a in plan["assets"]}
        review["critical_instances"] = [dict(empty(["qa/side-by-side.png"]), id=i["id"]) for i in plan["instances"] if assets[i["asset"]].get("critical")]
    if args.replace:
        archive_before_replace(root, dest)
    write_json(dest, review)
    return {"draft": "qa/review-draft.json", "note": "Inspect current images before filling scores and saving qa/review.json; null scores cannot pass"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("annotate", "register", "extract", "inspect", "audit", "compose", "compare", "verify", "status", "review-template", "preview", "pack"):
        sub = commands.add_parser(command)
        sub.add_argument("--run", required=True, type=Path)
        if command in ("status", "preview"):
            sub.add_argument("--mode", choices=("quick", "strict"), default="quick",
                             help="quick checks assets only; strict also verifies current visual evidence")
        if command in ("annotate", "extract"):
            group = sub.add_mutually_exclusive_group(required=True)
            group.add_argument("--round")
            group.add_argument("--all", action="store_true") if command == "annotate" else group.add_argument("--asset")
        if command == "register":
            sub.add_argument("--round", required=True)
        if command in ("extract", "register", "review-template", "preview", "pack"):
            sub.add_argument("--replace", action="store_true")
        if command == "extract":
            sub.add_argument("--normalize-size", action="store_true")
        if command == "inspect":
            group = sub.add_mutually_exclusive_group()
            group.add_argument("--asset")
            group.add_argument("--image", help="Inspect a raw image relative to --run")
        if command == "pack":
            sub.add_argument("--output", default="delivery/assets.zip")
        if command == "compare":
            sub.add_argument("--actual", default="assembly/reconstructed.png")
    args = parser.parse_args()
    root = args.run.resolve()
    plan = load_plan(root)
    if args.command in ("annotate", "register", "extract", "compare", "review-template"):
        result = {"annotate": annotate, "register": register, "extract": extract, "compare": compare,
                  "review-template": review_template}[args.command](root, plan, args)
    elif args.command in ("inspect", "preview", "pack"):
        from asset_delivery import inspect_images, preview, pack
        if args.command == "inspect":
            result = inspect_images(root, plan, args)
        elif args.command == "preview":
            result = preview(root, plan, args, status(root, plan, args.mode))
        else:
            result = pack(root, plan, args, verify(root, plan))
    elif args.command == "status":
        result = status(root, plan, args.mode)
    else:
        result = {"audit": audit, "compose": compose, "verify": verify, "status": status}[args.command](root, plan)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command != "preview" and (result.get("passed") is False or result.get("structural_passed") is False
                                      or result.get("strict_review") == "failed"):
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
