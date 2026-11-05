"""Shared local file and pixel primitives. No model or network calls."""
import hashlib
import json
import re
import shutil
from pathlib import Path

from PIL import Image


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or Path(name).is_absolute():
        raise ValueError(f"Path must stay relative to run directory: {name}")
    return path


def rgba(path):
    with Image.open(path) as image:
        return image.convert("RGBA")


def ints(value, count, positive=False):
    return (isinstance(value, list) and len(value) == count
            and all(type(x) is int and (not positive or x > 0) for x in value))


def intersects(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def unique(items, label):
    ids = [x["id"] for x in items]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", x) for x in ids):
        raise ValueError(f"Invalid or duplicate {label} ids")


def archive_before_replace(root, path):
    if path.exists():
        relative = path.relative_to(root)
        archive = root / "history" / relative.parent / f"{path.stem}-{sha(path)[:16]}{path.suffix}"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(path, archive)


def inside(box, size):
    return (ints(box, 4) and min(box[:2]) >= 0 and min(box[2:]) > 0
            and box[0] + box[2] <= size[0] and box[1] + box[3] <= size[1])


def crop_box(image, box):
    if not inside(box, image.size):
        raise ValueError(f"Crop outside actual source dimensions {list(image.size)}: {box}")
    x, y, w, h = box
    return image.crop((x, y, x + w, y + h))
