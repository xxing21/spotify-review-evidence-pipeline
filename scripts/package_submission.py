"""Build a sanitized public submission from saved evidence; no network/model calls."""
import gzip
import hashlib
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "submission/github"
sys.path.insert(0, str(ROOT))
from spotify_pipeline.common import now, write_json


def excluded(path):
    return (any(part in {".git", ".vercel", ".next", "node_modules", "__pycache__", ".venv"} for part in path.parts)
        or path.name == ".DS_Store" or path.suffix in {".pyc", ".tsbuildinfo"}
        or (path.name.startswith(".env") and path.name != ".env.example")
        or path.name.startswith("dashboard_upload_checkpoint")
        or path.name.startswith("local-reference")
        or path.name == "package_manifest.json"
        or ("production-100k-v1" in path.parts and path.name in {"enriched.jsonl", "run_log.jsonl"}))


def copy_tree(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.iterdir()):
        if excluded(path):
            continue
        target = destination / path.name
        if path.is_dir():
            if path.name == "handoffs" and "production-100k-v1" in path.parts:
                with tarfile.open(destination / "handoffs.tar.gz", "w:gz") as archive:
                    for member in sorted(path.glob("*.json")):
                        archive.add(member, arcname="handoffs/" + member.name)
                continue
            copy_tree(path, target)
        elif path.is_file():
            shutil.copy2(path, target)


def secret_values():
    values = []
    for env in [ROOT / ".env", ROOT / "dashboard-vercel/.env.local"]:
        if env.exists():
            for line in env.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if len(value) > 15:
                        values.append(value.encode())
    return values


def scan_bytes(data, path, values, problems):
    if any(secret in data for secret in values):
        problems.add(str(path) + ": configured secret value")
    if re.search(rb"postgres(?:ql)?://[^\s\"']+:[^\s\"']+@", data):
        problems.add(str(path) + ": embedded database credential")
    if re.search(rb"sk-(?:proj-)?[A-Za-z0-9_-]{45,}", data):
        problems.add(str(path) + ": API-key-shaped value")


def build():
    if (DEST / ".git").exists():
        raise ValueError("Refusing to rebuild an initialized publication checkout")
    DEST.mkdir(parents=True, exist_ok=True)
    for name in ["spotify_pipeline", "tests", "scripts", "docs", "cost", "evals", "artifacts", "dashboard-vercel"]:
        copy_tree(ROOT / name, DEST / name)
    copy_tree(ROOT / "submission/grading", DEST / "grading")
    for name in ["README.md", "README.dataset.md", "GRADING_CONTRACT.md", "COST_CALCULATOR.md",
        "pyproject.toml", ".gitignore", ".env.example", "check_submission.py", "prepare_dataset.py",
        "manifest.json", "cost_100.csv", "checkpoint_500.csv", "analysis_10000.csv", "golden_50_to_label.csv"]:
        shutil.copy2(ROOT / name, DEST / name)
    with (DEST / ".gitignore").open("a") as out:
        out.write("\nnode_modules/\n.next/\n.vercel/\n*.tsbuildinfo\nsubmission/\n")
    (DEST / "grading/README.md").write_text(
        "# Full-file accounting adapter\n\n100,000 completed nonempty source IDs; 13 empty-text quarantines; "
        "560,609 nonempty source IDs explicitly outside the 100k scope. All 660,622 IDs and hashes "
        "are accounted for, but they are not all classified. The full checker remains review_required "
        "for incomplete full classification and 48 requests with missing usage. See "
        "../evals/production_100k/full_file_self_check.json. Records and calls are gzip JSONL, "
        "supported directly by the supplied checker.\n", encoding="utf-8")


def main():
    if '--scan-only' not in sys.argv:
        build()
    problems = set()
    values = secret_values()
    manifest = []
    for path in sorted(DEST.rglob("*")):
        if not path.is_file() or excluded(path.relative_to(DEST)):
            continue
        relative = path.relative_to(DEST)
        data = path.read_bytes()
        scan_bytes(data, relative, values, problems)
        if path.name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as archive:
                for member in archive:
                    if member.isfile():
                        scan_bytes(archive.extractfile(member).read(), str(relative) + ":" + member.name, values, problems)
        elif path.suffix == ".gz":
            with gzip.open(path, "rb") as stream:
                scan_bytes(stream.read(), relative, values, problems)
        if len(data) >= 100 * 1024 * 1024:
            problems.add(str(relative) + ": exceeds GitHub file limit")
        manifest.append({"path": str(relative), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    if problems:
        raise ValueError("Public package scan failed: " + "; ".join(sorted(problems)))
    result = {"saved_at": now(), "passed": True, "file_count": len(manifest),
        "total_bytes": sum(row["bytes"] for row in manifest), "configured_secret_matches": 0,
        "credential_patterns": 0, "compressed_contents_scanned": True,
        "full_raw_csv_included": False, "operational_sqlite_included": False,
        "paid_model_calls": 0, "files": manifest}
    write_json(ROOT / "evals/production_100k/package_manifest.json", result)
    shutil.copy2(ROOT / "evals/production_100k/package_manifest.json", DEST / "evals/production_100k/package_manifest.json")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
