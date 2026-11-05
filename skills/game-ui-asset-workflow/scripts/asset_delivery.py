"""Alpha inspection, a dependency-free preview, and verified delivery archives."""
import shutil
import zipfile
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from asset_io import archive_before_replace, local, read_json, rgba, sha, write_json
from asset_processing import source_paths


def inspect_images(root, plan, args):
    assets = {a["id"]: a for a in plan["assets"]}
    if args.image:
        path = local(root, args.image)
        items = [("raw-" + sha(path)[:12], args.image)]
    elif args.asset:
        items = [(args.asset, assets[args.asset]["file"])]
    else:
        active = {i["asset"] for i in plan["instances"]}
        items = [(a["id"], a["file"]) for a in plan["assets"] if a.get("required", True) or a["id"] in active]
    results = []
    for key, name in items:
        try:
            image = rgba(local(root, name))
            alpha = image.getchannel("A")
            histogram = alpha.histogram()
            preview = Image.new("RGB", (image.width * 2, image.height))
            for index, color in enumerate(("#f5f2e9", "#20252c")):
                background = Image.new("RGBA", image.size, color)
                preview.paste(Image.alpha_composite(background, image).convert("RGB"), (index * image.width, 0))
            dest = f"qa/alpha/{key}.png"
            local(root, dest).parent.mkdir(parents=True, exist_ok=True)
            preview.save(local(root, dest))
            bounds = alpha.point(lambda v: 255 if v >= 16 else 0).getbbox()
            results.append({"id": key, "image": name, "sha256": sha(local(root, name)), "size": list(image.size),
                            "alpha_extrema": list(alpha.getextrema()), "nonzero_alpha_box": alpha.getbbox(),
                            "visible_alpha_box": bounds, "clear_pixels": sum(histogram[:3]),
                            "partial_pixels": sum(histogram[3:255]), "evidence": dest})
        except OSError as exc:
            results.append({"id": key, "error": str(exc)})
    previous_path = root / "qa/alpha-inspection.json"
    previous = read_json(previous_path).get("images", []) if previous_path.exists() else []
    merged = {row["id"]: row for row in previous + results}
    report = {"passed": all("error" not in row for row in results), "images": list(merged.values()),
              "note": "Light/dark evidence needs visual review; alpha statistics cannot detect painted checkerboards or halos"}
    write_json(root / "qa/alpha-inspection.json", report)
    return report


def preview(root, plan, args, state):
    dest = root / "preview"
    templates = Path(__file__).resolve().parent.parent / "assets/preview"
    outputs = ["index.html", "style.css", "app.js", "data.json"]
    if not args.replace and any((dest / name).exists() for name in outputs):
        raise ValueError("Preview exists; use --replace to refresh its snapshot")
    for name in outputs:
        if args.replace:
            archive_before_replace(root, dest / name)
    dest.mkdir(parents=True, exist_ok=True)

    def url(name):
        return "../" + quote(name.replace("\\", "/"), safe="/") if name and local(root, name).is_file() else None

    rows = {a["id"]: a for a in state["assets"]}
    assets = []
    for asset in plan["assets"]:
        assets.append(dict(asset, url=url(asset["file"]), status=rows[asset["id"]],
                           alpha_preview=url(f"qa/alpha/{asset['id']}.png"),
                           instances=[i for i in plan["instances"] if i["asset"] == asset["id"]],
                           sources=[{"path": name, "url": url(name)} for name in sorted(source_paths(root, plan, asset))]))
    rounds = [dict(r, raw_url=url(r.get("raw_image", r["image"])), image_url=url(r["image"]),
                   prompt_url=url(f"prompts/{r['id']}.md"), annotation_url=url(f"annotations/{r['id']}.png"),
                   recipe_url=url(r.get("recipe"))) for r in plan["rounds"]]
    data = {"canvas": plan["canvas"], "reference": url(plan["reference"]), "state": state,
            "assets": assets, "instances": plan["instances"], "regions": plan.get("regions", []), "rounds": rounds,
            "evidence": [{"path": p.relative_to(root).as_posix(), "url": url(p.relative_to(root).as_posix())}
                         for p in sorted((root / "qa").glob("*.png"))]}
    for name in outputs[:-1]:
        shutil.copy2(templates / name, dest / name)
    write_json(dest / "data.json", data)
    return {"preview": "preview/index.html", "phase": state["phase"],
            "note": "Serve the run directory over HTTP. Re-run preview --replace after changes; this is a snapshot."}


def pack(root, plan, args, acceptance):
    if not acceptance.get("passed"):
        raise ValueError("Delivery blocked: run verify successfully against current assets and evidence first")
    preview_data = root / "preview/data.json"
    if preview_data.exists():
        state = read_json(preview_data)["state"]
        if not state.get("review_current") or any(state.get(key) != acceptance.get(key) for key in ("state_sha256", "actual_sha256", "review_sha256")):
            raise ValueError("Preview snapshot is stale; refresh it with preview --mode strict --replace before packing")
    dest = local(root, args.output)
    if dest.suffix.lower() != ".zip":
        raise ValueError("Delivery output must be a .zip file inside --run")
    if dest.exists() and not args.replace:
        raise ValueError("Archive exists; use a new version or --replace")
    paths = {"plan.json", plan["reference"]}
    active = {i["asset"] for i in plan["instances"]}
    for asset in plan["assets"]:
        if not asset.get("required", True) and asset["id"] not in active:
            continue
        if local(root, asset["file"]).is_file():
            paths.add(asset["file"])
        paths.update(source_paths(root, plan, asset))
    for folder in ("annotations", "prompts", "recipes", "masks", "provenance", "assembly", "qa", "preview"):
        for path in (root / folder).rglob("*"):
            if path.is_file() and not any(part.startswith(".") or part in ("node_modules", "__pycache__") for part in path.relative_to(root).parts):
                paths.add(path.relative_to(root).as_posix())
    if any(local(root, name) == dest for name in paths):
        raise ValueError("Archive output conflicts with a required input")
    if args.replace:
        archive_before_replace(root, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(paths):
                archive.write(local(root, name), name)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != paths:
                raise ValueError("Archive integrity or file coverage check failed")
        temporary.replace(dest)
    finally:
        temporary.unlink(missing_ok=True)
    return {"archive": args.output, "sha256": sha(dest), "file_count": len(paths),
            "asset_count": sum(local(root, a["file"]).is_file() for a in plan["assets"])}
