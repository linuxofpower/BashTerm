#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "photos_folder"
PHOTOS = ROOT / "photos"
VIDEOS = ROOT / "videos"

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

EXPECTED = {
    "source_photos": 3108,
    "source_videos": 232,
    "duplicate_photos": 966,
    "duplicate_videos": 71,
    "final_photos": 2142,
    "final_videos": 161,
}


def classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in PHOTO_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    return "other"


def hashes(path: Path):
    sha = hashlib.sha256()
    blake = hashlib.blake2b()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            sha.update(chunk)
            blake.update(chunk)
    return sha.hexdigest(), blake.hexdigest()


def safe_member(name: str) -> Path:
    name = name.replace("\\", "/")
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise RuntimeError(f"Unsafe archive pathname: {name}")
    return rel


def collision_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    n = 1
    while True:
        candidate = target.with_name(f"{stem}__collision_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def extract_and_consume_archives():
    print("\n========================================")
    print("1. EXTRACT + CONSUME ARCHIVES")
    print("========================================")
    WORK.mkdir(parents=True, exist_ok=True)

    for archive in ARCHIVES:
        if not archive.exists():
            raise RuntimeError(f"Expected archive missing: {archive.name}")

        print(f"\n>>> {archive.name}")
        extracted_files = 0
        extracted_bytes = 0

        try:
            with zipfile.ZipFile(archive, "r") as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue

                    rel = safe_member(info.filename)
                    target = collision_path(WORK / rel)
                    target.parent.mkdir(parents=True, exist_ok=True)

                    with z.open(info, "r") as src, target.open("wb") as dst:
                        while True:
                            chunk = src.read(CHUNK)
                            if not chunk:
                                break
                            dst.write(chunk)

                    try:
                        dt = datetime(*info.date_time)
                        ts = dt.timestamp()
                        os.utime(target, (ts, ts))
                    except (ValueError, OSError):
                        pass

                    if target.stat().st_size != info.file_size:
                        raise RuntimeError(
                            f"Size verification failed: {target}\n"
                            f"expected={info.file_size} actual={target.stat().st_size}"
                        )

                    extracted_files += 1
                    extracted_bytes += info.file_size

        except Exception:
            print(f"\nFAILED: {archive.name}\nARCHIVE NOT DELETED.")
            raise

        size = archive.stat().st_size
        archive.unlink()
        print(f"OK: {extracted_files} files, {extracted_bytes / 1024**3:.2f} GiB extracted")
        print(f"DELETED ARCHIVE: {archive.name} ({size / 1024**3:.2f} GiB)")


def delete_thumbnail_trees():
    print("\n========================================")
    print("2. REMOVE .thumbnails")
    print("========================================")

    dirs = [
        p for p in WORK.rglob("*")
        if p.is_dir() and p.name.lower() == ".thumbnails"
    ]

    count = 0
    bytes_removed = 0

    for directory in dirs:
        files = [p for p in directory.rglob("*") if p.is_file()]
        for p in files:
            try:
                bytes_removed += p.stat().st_size
                count += 1
            except FileNotFoundError:
                pass
        print(f"DELETE TREE: {directory}")
        shutil.rmtree(directory)

    print(f".thumbnails removed: {count} files, {bytes_removed / 1024**2:.2f} MiB")


def count_media():
    result = defaultdict(int)
    for path in WORK.rglob("*"):
        if path.is_file():
            result[classify(path)] += 1
    return result


def deduplicate():
    print("\n========================================")
    print("3. DOUBLE-HASH DEDUPLICATION")
    print("========================================")

    before = count_media()
    print(
        f"Before dedup: {before['photo']} photos / "
        f"{before['video']} videos / {before['other']} other"
    )

    if (
        before["photo"] != EXPECTED["source_photos"]
        or before["video"] != EXPECTED["source_videos"]
        or before["other"] != 0
    ):
        raise RuntimeError(
            "PRE-DEDUP CONTRACT FAILED. Nothing has been deduplicated.\n"
            f"Expected: {EXPECTED['source_photos']} photos, "
            f"{EXPECTED['source_videos']} videos, 0 other\n"
            f"Actual: {before['photo']} photos, {before['video']} videos, "
            f"{before['other']} other"
        )

    by_size = defaultdict(list)
    for path in WORK.rglob("*"):
        if path.is_file():
            by_size[path.stat().st_size].append(path)

    delete_candidates = []
    seen = {}
    print("\nBuilding verified duplicate set...")

    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for path in sorted(paths):
            sha, blake = hashes(path)
            key = (size, sha, blake)
            if key in seen:
                delete_candidates.append((path, seen[key], classify(path), size, sha, blake))
            else:
                seen[key] = path

    candidate_counts = defaultdict(int)
    for _, _, kind, _, _, _ in delete_candidates:
        candidate_counts[kind] += 1

    print(
        "\nVerified candidates:"
        f"\n  photos: {candidate_counts['photo']}"
        f"\n  videos: {candidate_counts['video']}"
        f"\n  other:  {candidate_counts['other']}"
    )

    if (
        candidate_counts["photo"] != EXPECTED["duplicate_photos"]
        or candidate_counts["video"] != EXPECTED["duplicate_videos"]
        or candidate_counts["other"] != 0
    ):
        raise RuntimeError(
            "DEDUP CONTRACT FAILED. ZERO duplicate files deleted.\n"
            f"Expected: {EXPECTED['duplicate_photos']} photo + "
            f"{EXPECTED['duplicate_videos']} video duplicates\n"
            f"Actual: {candidate_counts['photo']} photo + "
            f"{candidate_counts['video']} video duplicates"
        )

    print("\nCONTRACT MATCHED.")
    print("Deleting verified duplicates...\n")

    reclaimed = 0
    for path, keep, kind, size, sha, blake in delete_candidates:
        print(f"DELETE {kind.upper()}: {path.relative_to(WORK)}")
        print(f"    KEEP: {keep.relative_to(WORK)}")
        path.unlink()
        reclaimed += size

    print(f"\nDeleted {len(delete_candidates)} duplicates")
    print(f"Reclaimed: {reclaimed / 1024**3:.2f} GiB")


def unique_final_path(directory: Path, source: Path) -> Path:
    target = directory / source.name
    if not target.exists():
        return target
    stem = source.stem
    suffix = source.suffix
    n = 1
    while True:
        candidate = directory / f"{stem}__{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def separate_media():
    print("\n========================================")
    print("4. SEPARATE PHOTOS / VIDEOS")
    print("========================================")

    PHOTOS.mkdir(exist_ok=True)
    VIDEOS.mkdir(exist_ok=True)

    files = [p for p in WORK.rglob("*") if p.is_file()]
    moved = defaultdict(int)

    for source in files:
        kind = classify(source)
        if kind == "photo":
            destination = unique_final_path(PHOTOS, source)
        elif kind == "video":
            destination = unique_final_path(VIDEOS, source)
        else:
            raise RuntimeError(f"Unexpected non-media file: {source}")
        shutil.move(str(source), str(destination))
        moved[kind] += 1

    print(f"Moved photos: {moved['photo']}")
    print(f"Moved videos: {moved['video']}")


def cleanup_work_tree():
    print("\n========================================")
    print("5. CLEAN WORK TREE")
    print("========================================")

    leftovers = [p for p in WORK.rglob("*") if p.is_file()]
    if leftovers:
        raise RuntimeError(
            f"Refusing to remove photos_folder: {len(leftovers)} files remain."
        )

    shutil.rmtree(WORK)
    print("Removed photos_folder/")


def final_verify():
    print("\n========================================")
    print("6. FINAL VERIFICATION")
    print("========================================")

    photos = sum(1 for p in PHOTOS.iterdir() if p.is_file())
    videos = sum(1 for p in VIDEOS.iterdir() if p.is_file())

    print(f"photos/: {photos}")
    print(f"videos/: {videos}")

    if photos != EXPECTED["final_photos"] or videos != EXPECTED["final_videos"]:
        raise RuntimeError(
            "FINAL COUNT DOES NOT MATCH CONTRACT.\n"
            f"Expected {EXPECTED['final_photos']} photos and "
            f"{EXPECTED['final_videos']} videos."
        )

    archives_left = [a.name for a in ARCHIVES if a.exists()]
    print(f"archives remaining: {len(archives_left)}")
    if archives_left:
        raise RuntimeError(f"Archives unexpectedly remain: {archives_left}")

    root_dirs = sorted(p.name for p in ROOT.iterdir() if p.is_dir())
    print(f"directories: {root_dirs}")

    print("\n========================================")
    print("SUCCESS")
    print("========================================")
    print(f"{photos} photos\n{videos} videos\n{photos + videos} total unique media files")


def main():
    print("LIVE PHOTO ARCHIVE CLEANUP")
    print(f"Root: {ROOT}")
    print("\nWARNING: THIS RUN DELETES ARCHIVES AND VERIFIED DUPLICATE MEDIA.\n")
    extract_and_consume_archives()
    delete_thumbnail_trees()
    deduplicate()
    separate_media()
    cleanup_work_tree()
    final_verify()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\nINTERRUPTED. Completed archive extractions may already have consumed their ZIP files.",
            file=sys.stderr,
        )
        sys.exit(130)
    except Exception as e:
        print(f"\nSTOPPED SAFELY:\n{e}", file=sys.stderr)
        sys.exit(1)
