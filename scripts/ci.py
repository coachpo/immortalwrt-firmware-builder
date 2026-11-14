#!/usr/bin/env python3
"""Local, testable helpers for firmware CI; no builds or external writes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent.parent
FIRMWARE_PREFIX = "immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod"
FIRMWARE_FILES = tuple(FIRMWARE_PREFIX + suffix for suffix in (
    "-bl31-uboot.fip",
    "-initramfs-recovery.itb",
    "-preloader.bin",
    "-squashfs-sysupgrade.itb",
    ".manifest",
))
PROVENANCE_FILES = ("build-info.json", "seed.config", "firmware.config", "feeds.conf")


def cache_outputs(environment, seed):
    safe = lambda value: re.sub(r"[^A-Za-z0-9._-]", "_", value)
    ref = safe(environment.get("IMMORTALWRT_REF") or "default")
    epoch = safe(environment.get("CACHE_EPOCH") or "v1")
    # Content identity belongs in cache keys; each run saves a fresh snapshot.
    seed_hash = hashlib.sha256(seed.read_bytes()).hexdigest()
    platform = f"{environment['RUNNER_OS']}-{environment['RUNNER_ARCH']}"
    run = f"{environment['GITHUB_RUN_ID']}-{environment['GITHUB_RUN_ATTEMPT']}"
    outputs = {}
    for kind in ("ccache", "dl"):
        target_prefix = f"{platform}-{kind}-tr3000-"
        ref_prefix = f"{target_prefix}{ref}-"
        prefix = f"{ref_prefix}{seed_hash}-{epoch}-"
        outputs.update({
            f"{kind}_key": prefix + run,
            f"{kind}_prefix": prefix,
            f"{kind}_ref_prefix": ref_prefix,
            f"{kind}_target_prefix": target_prefix,
        })
    return outputs


def require_files(source, names):
    invalid = [name for name in names
               if not (source / name).is_file() or (source / name).stat().st_size == 0]
    if invalid:
        raise ValueError("Missing or empty required files: " + ", ".join(invalid))


def collect_firmware(source, destination):
    require_files(source, FIRMWARE_FILES)
    # Validate the entire set before staging anything for upload or release.
    # A reused staging directory could add stale assets through the upload glob.
    destination.mkdir(parents=True, exist_ok=False)
    for name in FIRMWARE_FILES:
        shutil.copy2(source / name, destination / name)


def git_output(tree, *arguments):
    return subprocess.run(
        ["git", "-C", str(tree), *arguments],
        text=True, capture_output=True, check=True,
    ).stdout


def record_provenance(builder, tree, destination, environment):
    feeds = {}
    for feed in sorted((tree / "feeds").glob("*")):
        if (feed / ".git").exists():
            try:
                feeds[feed.name] = git_output(feed, "rev-parse", "HEAD").strip()
            except subprocess.CalledProcessError:
                # A failed feed clone may leave a repository without HEAD.
                feeds[feed.name] = None
    info = {
        "builder_commit": git_output(builder, "rev-parse", "HEAD").strip(),
        "immortalwrt_commit": git_output(tree, "rev-parse", "HEAD").strip(),
        "requested_ref": environment.get("IMMORTALWRT_REF") or "default branch",
        "source_submodules": git_output(tree, "submodule", "status", "--recursive").strip(),
        "feeds": feeds,
        "config_available": (tree / ".config").is_file(),
        "configuration_outcome": environment.get("CONFIGURATION_OUTCOME"),
        "compilation_outcome": environment.get("COMPILATION_OUTCOME"),
        "run_id": environment.get("GITHUB_RUN_ID"),
        "run_attempt": environment.get("GITHUB_RUN_ATTEMPT"),
        "runner_os": environment.get("RUNNER_OS"),
        "runner_arch": environment.get("RUNNER_ARCH"),
        "runner_image": environment.get("ImageOS"),
        "runner_image_version": environment.get("ImageVersion"),
        "run_url": "{}/{}/actions/runs/{}".format(
            environment.get("GITHUB_SERVER_URL", "https://github.com"),
            environment.get("GITHUB_REPOSITORY", ""),
            environment.get("GITHUB_RUN_ID", ""),
        ),
    }
    patch = git_output(tree, "diff", "--binary", "HEAD", "--")
    info["source_modified"] = bool(patch)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
    shutil.copy2(builder / "tr3000/seed.config", destination / "seed.config")
    for original, name in ((".config", "firmware.config"), ("feeds.conf", "feeds.conf")):
        if (tree / original).is_file():
            shutil.copy2(tree / original, destination / name)
    # The source commit alone omits the helper's tracked source-mirror edits.
    if patch:
        (destination / "source.patch").write_text(patch)


def verify_provenance(source, builder_commit):
    require_files(source, PROVENANCE_FILES)
    info = json.loads((source / "build-info.json").read_text())
    if info["builder_commit"] != builder_commit:
        raise ValueError("Provenance builder commit does not match the release checkout")
    if (info["configuration_outcome"], info["compilation_outcome"]) != ("success", "success"):
        raise ValueError("Cannot release provenance from an unsuccessful configuration or build")
    if not info["config_available"] or not info["immortalwrt_commit"] or not info["feeds"]:
        raise ValueError("Incomplete source, feed or configuration provenance")
    if any(commit is None for commit in info["feeds"].values()):
        raise ValueError("Feed provenance contains an unresolved revision")
    if info["source_modified"]:
        require_files(source, ("source.patch",))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("cache-keys")
    collect = commands.add_parser("collect")
    collect.add_argument("source", type=Path)
    collect.add_argument("destination", type=Path)
    provenance = commands.add_parser("provenance")
    provenance.add_argument("tree", type=Path)
    provenance.add_argument("destination", type=Path)
    verify = commands.add_parser("verify-provenance")
    verify.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "cache-keys":
            for key, value in cache_outputs(os.environ, ROOT / "tr3000/seed.config").items():
                print(f"{key}={value}")
        elif args.command == "collect":
            collect_firmware(args.source, args.destination)
        elif args.command == "provenance":
            record_provenance(ROOT, args.tree, args.destination, os.environ)
        else:
            verify_provenance(args.source, git_output(ROOT, "rev-parse", "HEAD").strip())
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"CI preparation failed: {error}\n")


if __name__ == "__main__":
    main()
