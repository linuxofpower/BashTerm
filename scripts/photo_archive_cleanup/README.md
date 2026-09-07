# Photo Archive Cleanup

Small Python utilities for consolidating ZIP-based photo/video archives directly into a live working directory when disk space is limited.

## Files

- `photo_dryrun.py` — initial SHA-256 dry run. Scans the existing `photos_folder/` plus configured ZIP archives without extracting, moving, or deleting anything.
- `photo_dryrun_hardened.py` — hardened dry run using file size + SHA-256 + BLAKE2b. Produces source counts, duplicate counts, expected survivor counts, `.thumbnails` counts, and a compact preflight fingerprint.
- `photo_live.py` — destructive in-place pipeline. Extracts one archive at a time, deletes each archive only after that archive completed extraction, removes `.thumbnails`, double-hash deduplicates, then separates media into `photos/` and `videos/`.

## Important

These scripts are currently configured for one specific archive layout:

```text
photos_folder/
2018_drive_photos.zip
photos_part_1.zip
photos_part_2.zip
photos_part_3.zip
photos_part_4.zip
```

They resolve paths relative to the script location, so for direct reuse either copy the selected script into the directory containing those archives or edit `ROOT`, `LIVE`/`WORK`, and `ARCHIVES`.

`photo_live.py` also contains a dataset-specific `EXPECTED` contract. Do **not** reuse it destructively on another archive set without first running the hardened dry run and replacing those expected counts.

## Duplicate policy

Automatic duplicate deletion is based on exact content identity:

```text
same size + same SHA-256 + same BLAKE2b
```

Filename and filesystem/ZIP metadata are useful evidence, but they are not treated as proof of duplicate content.

Same-name files with different bytes are preserved by assigning collision-safe temporary names during extraction.

## Low-space live workflow

The destructive script intentionally works archive-by-archive:

```text
ZIP 1 -> extract completely -> verify member sizes/CRC while reading -> delete ZIP 1
ZIP 2 -> extract completely -> delete ZIP 2
...
all ZIPs consumed
-> remove .thumbnails
-> build complete double-hash duplicate candidate set
-> verify candidate counts against dry-run contract
-> delete verified duplicates
-> move survivors to photos/ and videos/
-> remove empty photos_folder/
-> verify final counts
```

A failed archive extraction leaves that archive in place. An interruption after a successfully completed archive may occur after that archive has already been deleted, so the extracted working tree becomes the surviving copy for that archive.

## Recommended procedure

1. Run the initial dry run if investigating the dataset.
2. Run `photo_dryrun_hardened.py` and save the reported counts/fingerprint.
3. Review any `other` files and `.thumbnails` findings.
4. Put the confirmed source/duplicate/final counts into `EXPECTED` in `photo_live.py`.
5. Run the live script only when the dry-run contract is understood and accepted.

Example:

```bash
python photo_dryrun_hardened.py
python photo_live.py
```

## Example validated contract (2026-09-07)

The original run that motivated these utilities produced:

```text
P=3108;V=232;O=0;DP=966;DV=71;DO=0;FP=2142;FV=161;T=0
fingerprint: 4a66dc62b9cd3988e61245ed7cb13fad70522489cb85aa01e78d7052f668e55a
```

Expected final media for that specific dataset:

```text
photos/: 2142
videos/: 161
```

These numbers are historical test evidence, not safe defaults for another library.
