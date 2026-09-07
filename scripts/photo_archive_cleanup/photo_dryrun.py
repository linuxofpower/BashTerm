#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import zipfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "photos_folder"

ARCHIVES = [
    ROOT / "2018_drive_photos.zip",
    ROOT / "photos_part_1.zip",
    ROOT / "photos_part_2.zip",
    ROOT / "photos_part_3.zip",
    ROOT / "photos_part_4.zip",
]

PHOTO_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".heic", ".heif", ".bmp", ".tif", ".tiff",
    ".dng", ".raw", ".cr2", ".cr3", ".nef",
    ".arw", ".orf", ".rw2", ".avif",
}

VIDEO_EXTS = {
    ".mp4", ".mov", ".m4v", ".avi", ".mkv",
    ".webm", ".3gp", ".3g2", ".mts", ".m2ts",
    ".mpg", ".mpeg", ".wmv",
}

CHUNK = 4 * 1024 * 1024


def classify(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in PHOTO_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    return "other"


def is_thumbnail(path: str) -> bool:
    parts = [p.lower() for p in Path(path.replace("\\", "/")).parts]
    return ".thumbnails" in parts


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def hash_zip_member(z: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    h = hashlib.sha256()
    with z.open(info) as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def main():
    seen = {}
    totals = defaultdict(int)
    duplicates = defaultdict(int)
    duplicate_bytes = defaultdict(int)
    thumbnails = defaultdict(int)
    thumbnail_bytes = defaultdict(int)
    others = []
    collisions = []

    print("=== DRY RUN ===")
    print("Nothing will be extracted, moved, or deleted.\n")

    if LIVE.exists():
        print(f"Scanning live folder: {LIVE}")
        for path in sorted(LIVE.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(LIVE).as_posix()
            kind = classify(rel)
            size = path.stat().st_size
            totals[kind] += 1
            if is_thumbnail(rel):
                thumbnails[kind] += 1
                thumbnail_bytes[kind] += size
                continue
            digest = hash_file(path)
            record = {
                "source": "live",
                "name": rel,
                "basename": path.name,
                "size": size,
                "mtime": path.stat().st_mtime,
                "kind": kind,
            }
            key = (size, digest)
            if key in seen:
                original = seen[key]
                duplicates[kind] += 1
                duplicate_bytes[kind] += size
                if original["basename"] != record["basename"]:
                    collisions.append((original["name"], record["name"], size))
            else:
                seen[key] = record
            if kind == "other":
                others.append(("live", rel, size))

    for archive in ARCHIVES:
        if not archive.exists():
            print(f"Missing: {archive.name}")
            continue
        print(f"Scanning archive: {archive.name}")
        with zipfile.ZipFile(archive) as z:
            bad = z.testzip()
            if bad:
                raise RuntimeError(f"{archive.name}: damaged member: {bad}")
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                kind = classify(name)
                size = info.file_size
                totals[kind] += 1
                if is_thumbnail(name):
                    thumbnails[kind] += 1
                    thumbnail_bytes[kind] += size
                    continue
                digest = hash_zip_member(z, info)
                record = {
                    "source": archive.name,
                    "name": name,
                    "basename": Path(name).name,
                    "size": size,
                    "mtime": info.date_time,
                    "crc": info.CRC,
                    "kind": kind,
                }
                key = (size, digest)
                if key in seen:
                    original = seen[key]
                    duplicates[kind] += 1
                    duplicate_bytes[kind] += size
                    if original["basename"] != record["basename"]:
                        collisions.append((original["name"], record["name"], size))
                else:
                    seen[key] = record
                if kind == "other":
                    others.append((archive.name, name, size))

    print("\n==============================")
    print("SOURCE CONTENT")
    print("==============================")
    print(f"Photos: {totals['photo']}")
    print(f"Videos: {totals['video']}")
    print(f"Other:  {totals['other']}")

    print("\n==============================")
    print("EXACT DUPLICATES")
    print("==============================")
    print(f"Photos to delete: {duplicates['photo']} ({duplicate_bytes['photo'] / 1024**3:.2f} GiB)")
    print(f"Videos to delete: {duplicates['video']} ({duplicate_bytes['video'] / 1024**3:.2f} GiB)")
    print(f"Other duplicates: {duplicates['other']} ({duplicate_bytes['other'] / 1024**3:.2f} GiB)")

    print("\n==============================")
    print(".THUMBNAILS")
    print("==============================")
    thumb_count = sum(thumbnails.values())
    thumb_bytes = sum(thumbnail_bytes.values())
    print(f"Files to delete: {thumb_count}")
    print(f"Space: {thumb_bytes / 1024**3:.2f} GiB")

    unique_photos = totals["photo"] - duplicates["photo"] - thumbnails["photo"]
    unique_videos = totals["video"] - duplicates["video"] - thumbnails["video"]

    print("\n==============================")
    print("EXPECTED FINAL LIBRARY")
    print("==============================")
    print(f"photos/: {unique_photos}")
    print(f"videos/: {unique_videos}")

    print("\n==============================")
    print("NON PHOTO/VIDEO FILES")
    print("==============================")
    print(f"Found: {len(others)}")

    print("\n==============================")
    print("SAME CONTENT / DIFFERENT NAMES")
    print("==============================")
    print(f"Cases: {len(collisions)}")

    print("\nDRY RUN COMPLETE.")
    print("No files were changed.")


if __name__ == "__main__":
    main()
