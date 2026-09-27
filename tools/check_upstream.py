#!/usr/bin/env python3
"""Report upstream changes in OpenScan3 / OpenScan3-Client since the recorded baseline.

Keeps blobless clones of the upstream repositories in a cache directory
outside this repo (default: <system temp>/os3-focus-stacking-upstream),
fetches them, and reports commits and diff stats touching the files this
project depends on, as listed in tools/upstream-baseline.json.

After reviewing the changes (and updating the spec/code if needed), move the
baseline forward by editing "baseline" and "checkedOn" in that file.

Exit codes: 0 = watched files unchanged, 1 = watched files changed, 2 = error.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE_FILE = Path(__file__).with_name("upstream-baseline.json")
DEFAULT_CACHE = Path(tempfile.gettempdir()) / "os3-focus-stacking-upstream"


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.rstrip()


def update_clone(url: str, path: Path) -> None:
    if path.exists():
        git("fetch", "--quiet", "--tags", "--prune", "origin", cwd=path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Blobless clone: history and trees only, file contents are fetched on demand.
        git("clone", "--quiet", "--no-checkout", "--filter=blob:none", url, str(path))


def report_repo(name: str, spec: dict, cache: Path, show_diff: bool) -> bool:
    """Print the report for one repository; return True if watched files changed."""
    path = cache / name
    update_clone(spec["url"], path)

    upstream = f"origin/{spec['branch']}"
    baseline = spec["baseline"]
    watch = spec["watch"]

    print(f"== {name} ({spec['branch']}) ==")
    print(f"baseline : {git('log', '-1', '--format=%h %cs %s', baseline, cwd=path)}")
    print(f"upstream : {git('log', '-1', '--format=%h %cs %s', upstream, cwd=path)}")
    newest_tag = git(
        "for-each-ref", "--sort=-creatordate", "--count=1", "--format=%(refname:short) %(creatordate:short)", "refs/tags",
        cwd=path,
    )
    print(f"newest tag: {newest_tag or '-'}")

    is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, upstream], cwd=path
    ).returncode == 0
    if not is_ancestor:
        print("WARNING  : baseline is not an ancestor of upstream (history rewritten?)")

    total = git("rev-list", "--count", f"{baseline}..{upstream}", cwd=path)
    print(f"commits since baseline: {total}")

    touching = git("log", "--format=  %h %cs %s", f"{baseline}..{upstream}", "--", *watch, cwd=path)
    stat = git("diff", "--stat", baseline, upstream, "--", *watch, cwd=path)
    if not stat:
        print("watched files: unchanged\n")
        return False

    print("watched files CHANGED:")
    print(stat)
    if touching:
        print("commits touching watched files:")
        print(touching)
    if show_diff:
        print(git("diff", baseline, upstream, "--", *watch, cwd=path))
    print()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help=f"clone cache (default: {DEFAULT_CACHE})")
    parser.add_argument("--diff", action="store_true", help="also print the full diff of watched files")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # utf-8-sig: tolerate a BOM added by Windows editors.
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8-sig"))
    print(f"baseline file checked on {baseline['checkedOn']}, cache: {args.cache}\n")

    try:
        changed = [
            report_repo(name, spec, args.cache, args.diff) for name, spec in baseline["repos"].items()
        ]
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {' '.join(exc.cmd)}\n{exc.stderr}", file=sys.stderr)
        return 2
    return 1 if any(changed) else 0


if __name__ == "__main__":
    sys.exit(main())
