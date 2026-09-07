#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import zipfile
from collections import defaultdict
from dataclasses import dataclass
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


@dataclass
class Record:
    source: str
    name: str
    basename: str
    size: int
    kind: str
    sha256: str
    blake2b: str
    metadata: str


def classify(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in PHOTO_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    return "other"


def is_thumbnail(name: str) -> bool:
    parts = [part.lower() for part in Path(name.replace("\\", "/")).parts]
    return ".thumbnails" in parts


def hash_stream(stream):
    sha = hashlib.sha256()
    blake = hashlib.blake2b()
    while True:
        chunk = stream.read(CHUNK)
        if not chunk:
            break
        sha.update(chunk)
        blake.update(chunk)
    return sha.hexdigest(), blake.hexdigest()


def hash_file(path: Path):
    with path.open("rb") as f:
        return hash_stream(f)


def gib(n: int) -> float:
    return n / 1024**3


def mib(n: int) -> float:
    return n / 1024**2


def main():
    totals = defaultdict(int)
    total_bytes = defaultdict(int)
    duplicate_count = defaultdict(int)
    duplicate_bytes = defaultdict(int)
    thumbnail_count = defaultdict(int)
    thumbnail_bytes = defaultdict(int)
    survivors = defaultdict(int)
    survivor_bytes = defaultdict(int)
    others = []
    same_content_different_name = []
    seen: dict[tuple[int, str, str], Record] = {}

    print("========================================")
    print("PHOTO LIBRARY HARDENED DRY RUN")
    print("========================================")
    print("NO extraction")
    print("NO moves")
    print("NO deletion")
    print()

    if LIVE.exists():
        print(f"[LIVE] {LIVE}")
        for path in sorted(LIVE.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(LIVE).as_posix()
            kind = classify(rel)
            stat = path.stat()
            size = stat.st_size
            totals[kind] += 1
            total_bytes[kind] += size
            if is_thumbnail(rel):
                thumbnail_count[kind] += 1
                thumbnail_bytes[kind] += size
                continue
            sha256, blake2b = hash_file(path)
            rec = Record(
                source="LIVE",
                name=rel,
                basename=path.name,
                size=size,
                kind=kind,
                sha256=sha256,
                blake2b=blake2b,
                metadata=f"mtime_ns={stat.st_mtime_ns} mode={oct(stat.st_mode)}",
            )
            key = (size, sha256, blake2b)
            if key in seen:
                original = seen[key]
                duplicate_count[kind] += 1
                duplicate_bytes[kind] += size
                if original.basename != rec.basename:
                    same_content_different_name.append((original, rec))
            else:
                seen[key] = rec
                survivors[kind] += 1
                survivor_bytes[kind] += size
            if kind == "other":
                others.append(rec)

    for archive in ARCHIVES:
        if not archive.exists():
            print(f"[MISSING] {archive.name}")
            continue
        print(f"[ZIP]  {archive.name}")
        with zipfile.ZipFile(archive) as z:
            bad = z.testzip()
            if bad is not None:
                raise RuntimeError(f"{archive.name}: corrupt member: {bad}")
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                kind = classify(name)
                size = info.file_size
                totals[kind] += 1
                total_bytes[kind] += size
                if is_thumbnail(name):
                    thumbnail_count[kind] += 1
                    thumbnail_bytes[kind] += size
                    continue
                with z.open(info, "r") as stream:
                    sha256, blake2b = hash_stream(stream)
                rec = Record(
                    source=archive.name,
                    name=name,
                    basename=Path(name).name,
                    size=size,
                    kind=kind,
                    sha256=sha256,
                    blake2b=blake2b,
                    metadata=(
                        f"zip_mtime={info.date_time} crc32={info.CRC:08x} "
                        f"compressed={info.compress_size}"
                    ),
                )
                key = (size, sha256, blake2b)
                if key in seen:
                    original = seen[key]
                    duplicate_count[kind] += 1
                    duplicate_bytes[kind] += size
                    if original.basename != rec.basename:
                        same_content_different_name.append((original, rec))
                else:
                    seen[key] = rec
                    survivors[kind] += 1
                    survivor_bytes[kind] += size
                if kind == "other":
                    others.append(rec)

    print("\n========================================")
    print("SOURCE")
    print("========================================")
    for kind in ("photo", "video", "other"):
        print(f"{kind:6}: {totals[kind]:6}   {gib(total_bytes[kind]):8.2f} GiB")

    print("\n========================================")
    print("VERIFIED BYTE-IDENTICAL DUPLICATES")
    print("size + SHA-256 + BLAKE2b")
    print("========================================")
    for kind in ("photo", "video", "other"):
        print(
            f"{kind:6}: {duplicate_count[kind]:6} delete   "
            f"{gib(duplicate_bytes[kind]):8.2f} GiB"
        )

    print("\n========================================")
    print(".THUMBNAILS")
    print("========================================")
    thumbs_total = sum(thumbnail_count.values())
    thumbs_bytes = sum(thumbnail_bytes.values())
    print(f"delete: {thumbs_total} files ({gib(thumbs_bytes):.2f} GiB)")
    for kind in ("photo", "video", "other"):
        print(f"  {kind:6}: {thumbnail_count[kind]:6} ({mib(thumbnail_bytes[kind]):.2f} MiB)")

    print("\n========================================")
    print("EXPECTED FINAL MEDIA")
    print("========================================")
    print(f"photos/: {survivors['photo']} ({gib(survivor_bytes['photo']):.2f} GiB)")
    print(f"videos/: {survivors['video']} ({gib(survivor_bytes['video']):.2f} GiB)")

    print("\n========================================")
    print("OTHER FILE TYPES")
    print("========================================")
    print(f"count: {len(others)}")

    print("\n========================================")
    print("IDENTICAL CONTENT / DIFFERENT BASENAME")
    print("========================================")
    print(f"count: {len(same_content_different_name)}")

    fingerprint = hashlib.sha256()
    summary = (
        f"P={totals['photo']};V={totals['video']};O={totals['other']};"
        f"DP={duplicate_count['photo']};DV={duplicate_count['video']};"
        f"DO={duplicate_count['other']};FP={survivors['photo']};"
        f"FV={survivors['video']};T={thumbs_total}"
    )
    fingerprint.update(summary.encode())

    print("\n========================================")
    print("PREFLIGHT")
    print("========================================")
    print(summary)
    print(f"fingerprint: {fingerprint.hexdigest()}")
    print("\nDRY RUN COMPLETE — NOTHING CHANGED.")


if __name__ == "__main__":
    main()
