"""Measured registration, UI nine-slice and masked background reconstruction."""
import math

from PIL import Image, ImageFilter

from asset_io import (archive_before_replace, crop_box, inside, local, read_json,
                      rgba, sha, write_json)


def strategy(asset):
    return asset.get("strategy", "generate" if asset.get("round") else "local")


def sheet_canvas(plan, round_info):
    """Registered sheet pixels; legacy rounds inherit the final scene canvas."""
    return round_info.get("canvas", plan["canvas"])


def recipe_inputs(recipe):
    return {op[key] for op in recipe["operations"] for key in ("source", "base", "mask") if key in op}


def source_paths(root, plan, asset):
    paths = set(asset.get("source_files", []))
    if asset.get("round"):
        round_info = next(r for r in plan["rounds"] if r["id"] == asset["round"])
        paths.add(round_info["image"])
        paths.add(f"prompts/{round_info['id']}.md")
        if round_info.get("raw_image"):
            paths.add(round_info["raw_image"])
        if round_info.get("recipe"):
            paths.add(round_info["recipe"])
            recipe_path = local(root, round_info["recipe"])
            if recipe_path.exists():
                paths.update(recipe_inputs(read_json(recipe_path)))
    elif strategy(asset) == "crop":
        paths.add(asset["source"]["file"])
    return paths


def snapshot(root, paths):
    return {name: sha(local(root, name)) for name in sorted(paths)}


def registration_errors(root, plan, round_info):
    if not round_info.get("recipe"):
        return []
    path = root / "provenance/registration.json"
    records = read_json(path) if path.exists() else {}
    record = records.get(round_info["id"], {})
    recipe = read_json(local(root, round_info["recipe"]))
    inputs = recipe_inputs(recipe) | {round_info["recipe"], f"prompts/{round_info['id']}.md"}
    if round_info.get("raw_image"):
        inputs.add(round_info["raw_image"])
    expected = {"image": round_info["image"], "image_sha256": sha(local(root, round_info["image"])),
                "inputs": snapshot(root, inputs), "canvas": sheet_canvas(plan, round_info),
                "targets": {a["id"]: a["sheet_box"] for a in plan["assets"] if a.get("round") == round_info["id"]}}
    return [f"Missing or stale registration: {key}" for key, value in expected.items() if record.get(key) != value]


def uniform_landmarks(pairs, tolerance):
    if len(pairs) < 2 or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("At least two measured landmark pairs and a nonnegative tolerance are required")
    for pair in pairs:
        if any(len(pair[k]) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in pair[k])
               for k in ("source", "target")):
            raise ValueError("Landmarks must contain finite 2D points")
    count = len(pairs)
    a = [sum(p["source"][i] for p in pairs) / count for i in (0, 1)]
    b = [sum(p["target"][i] for p in pairs) / count for i in (0, 1)]
    denominator = sum(sum((p["source"][i] - a[i]) ** 2 for i in (0, 1)) for p in pairs)
    if not denominator:
        raise ValueError("Source landmarks must be distinct")
    scale = sum(sum((p["source"][i] - a[i]) * (p["target"][i] - b[i]) for i in (0, 1)) for p in pairs) / denominator
    offset = [b[i] - scale * a[i] for i in (0, 1)]
    error = max(math.dist([scale * p["source"][i] + offset[i] for i in (0, 1)], p["target"]) for p in pairs)
    if scale <= 0 or error > tolerance:
        raise ValueError(f"Landmarks cannot be aligned with uniform scale/translation; residual {error:.2f}px")
    return scale, offset, error


def nine_slice(image, size, borders, uniform_scale):
    if (len(borders) != 4 or any(type(v) is not int or v < 0 for v in borders)
            or not math.isfinite(uniform_scale) or uniform_scale <= 0):
        raise ValueError("Invalid nine-slice borders or uniform scale")
    left, top, right, bottom = borders
    if left + right >= image.width or top + bottom >= image.height:
        raise ValueError("Nine-slice requires a nonempty center")
    scaled = (max(1, round(image.width * uniform_scale)), max(1, round(image.height * uniform_scale)))
    image = image.resize(scaled, Image.Resampling.LANCZOS)
    left, top, right, bottom = [round(v * uniform_scale) for v in borders]
    if left + right >= image.width or top + bottom >= image.height:
        raise ValueError("Uniform scale collapses the nine-slice center")
    if left + right >= size[0] or top + bottom >= size[1]:
        raise ValueError("Target would crush nine-slice corners")
    sx, sy = [0, left, image.width - right, image.width], [0, top, image.height - bottom, image.height]
    tx, ty = [0, left, size[0] - right, size[0]], [0, top, size[1] - bottom, size[1]]
    result = Image.new("RGBA", tuple(size))
    for row in range(3):
        for col in range(3):
            source = (sx[col], sy[row], sx[col + 1], sy[row + 1])
            target = (tx[col + 1] - tx[col], ty[row + 1] - ty[row])
            if min(target) <= 0 or source[2] <= source[0] or source[3] <= source[1]:
                continue
            patch = image.crop(source).resize(target, Image.Resampling.LANCZOS)
            result.alpha_composite(patch, (tx[col], ty[row]))
    return result


def register(root, plan, args):
    round_info = next((r for r in plan["rounds"] if r["id"] == args.round), None)
    if not round_info or not round_info.get("recipe"):
        raise ValueError("Round needs a saved recipe before registration")
    recipe = read_json(local(root, round_info["recipe"]))
    assets = {a["id"]: a for a in plan["assets"] if a.get("round") == args.round}
    operations = recipe["operations"]
    if sorted(op["asset"] for op in operations) != sorted(assets):
        raise ValueError("Recipe must process each active round asset exactly once")
    dest = local(root, round_info["image"])
    inputs = recipe_inputs(recipe) | {round_info["recipe"], f"prompts/{args.round}.md"}
    if round_info.get("raw_image"):
        inputs.add(round_info["raw_image"])
    if any(local(root, name) == dest for name in inputs):
        raise ValueError("Registration output cannot overwrite any raw input")
    if dest.exists() and not args.replace:
        raise ValueError("Registered output exists; use a versioned path or --replace")
    before = snapshot(root, inputs)
    sheet = Image.new("RGBA", tuple(sheet_canvas(plan, round_info)))
    transforms = []
    for op in operations:
        asset = assets[op["asset"]]
        tile = Image.new("RGBA", sheet.size)
        source = rgba(local(root, op["source"]))
        kind = op["type"]
        if kind == "inpaint":
            if asset["kind"] != "background":
                raise ValueError("Masked inpainting is only a background-plate operation")
            base = rgba(local(root, op["base"]))
            with Image.open(local(root, op["mask"])) as mask_file:
                if mask_file.mode not in ("1", "L"):
                    raise ValueError("Inpaint mask must be a real grayscale image: white=repaint, black=preserve")
                mask = mask_file.convert("L")
            if source.size != sheet.size or base.size != sheet.size or mask.size != sheet.size:
                raise ValueError("Background, base and mask must match the round canvas")
            if not mask.getbbox():
                raise ValueError("Inpaint mask is empty")
            feather = op.get("feather", 0)
            if type(feather) not in (int, float) or not math.isfinite(feather) or feather < 0:
                raise ValueError("Invalid feather radius")
            if feather:
                mask = mask.filter(ImageFilter.GaussianBlur(feather))
            tile = Image.composite(source, base, mask)
            detail = {"type": kind, "mask": op["mask"], "feather": feather}
        else:
            crop = crop_box(source, op["source_box"])
            if kind == "nine-slice":
                if asset["kind"] not in ("button", "panel", "geometry"):
                    raise ValueError("Nine-slice is restricted to UI plates; never warp characters or icons")
                target = op.get("target_box", asset["sheet_box"])
                if not inside(target, sheet.size):
                    raise ValueError("Invalid target_box")
                crop = nine_slice(crop, target[2:], op["borders"], op.get("uniform_scale", 1))
                xy = target[:2]
                detail = {"type": kind, "target_box": target, "borders": op["borders"], "uniform_scale": op.get("uniform_scale", 1)}
            elif kind == "place":
                if op.get("landmarks"):
                    scale, offset, error = uniform_landmarks(op["landmarks"], op.get("max_error_px", 2))
                    xy = [round(op["source_box"][i] * scale + offset[i]) for i in (0, 1)]
                    size = [max(1, round(v * scale)) for v in crop.size]
                    detail = {"type": kind, "uniform_scale": scale, "offset": offset, "landmark_error_px": error}
                else:
                    target = op.get("target_box", asset["sheet_box"])
                    if not inside(target, sheet.size):
                        raise ValueError("Invalid target_box")
                    scale = min(target[2] / crop.width, target[3] / crop.height)
                    size = [max(1, round(v * scale)) for v in crop.size]
                    xy = [target[i] + (target[i + 2] - size[i]) // 2 for i in (0, 1)]
                    detail = {"type": kind, "uniform_scale": scale, "target_box": target}
                if not inside(list(xy) + size, sheet.size):
                    raise ValueError("Registration would cut off the source crop at a canvas edge")
                crop = crop.resize(size, Image.Resampling.LANCZOS)
            else:
                raise ValueError(f"Unknown recipe operation: {kind}")
            tile.alpha_composite(crop, tuple(xy))
            detail.update(source_box=op["source_box"], placed_at=xy, content_size=list(crop.size))
        # This is measurement only: keep the original alpha values in the saved tile.
        alpha = tile.getchannel("A").point(lambda value: 255 if value >= 16 else 0)
        bounds = alpha.getbbox()
        x, y, w, h = asset["sheet_box"]
        if not bounds or bounds[0] < x or bounds[1] < y or bounds[2] > x + w or bounds[3] > y + h:
            raise ValueError(f"Registered content falls outside the fixed planned asset box: {asset['id']}")
        sheet.alpha_composite(tile)
        transforms.append(dict(detail, asset=asset["id"], source_size=list(source.size)))
    if before != snapshot(root, inputs):
        raise ValueError("Inputs changed during registration")
    if args.replace:
        archive_before_replace(root, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest)
    path = root / "provenance/registration.json"
    records = read_json(path) if path.exists() else {}
    if path.exists():
        archive_before_replace(root, path)
    records[args.round] = {"image": round_info["image"], "image_sha256": sha(dest), "canvas": sheet_canvas(plan, round_info),
                          "inputs": before, "targets": {a["id"]: a["sheet_box"] for a in assets.values()},
                          "transforms": transforms}
    write_json(path, records)
    return {"round": args.round, "registered": round_info["image"], "asset_count": len(operations), "inputs": before}
