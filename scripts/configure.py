#!/usr/bin/env python3
"""Configure a TR3000 ImmortalWrt source tree; does not compile firmware."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent.parent
VANTAGE_REV = "0f8d16f2ce25132e6a074575af16468524d2d5dd"  # v1.0.20
VANTAGE_FEED = (
    "src-git vantage https://github.com/anothaDev/luci-theme-vantage.git^"
    + VANTAGE_REV
)
# Keep source downloads on project-operated endpoints, not regional mirrors.
PROJECT_MIRRORS = {
    "@GITHUB": ["https://raw.githubusercontent.com"],
    "@DEBIAN": ["https://ftp.debian.org/debian"],
    "@APACHE": ["https://dlcdn.apache.org", "https://archive.apache.org/dist"],
    "@GNU": ["https://ftpmirror.gnu.org", "https://ftp.gnu.org/gnu"],
    "@KERNEL": ["https://cdn.kernel.org/pub"],
    "@GNOME": ["https://download.gnome.org/sources"],
}


def prepare_source(tree):
    feeds = tree / "feeds.conf"
    original = feeds if feeds.exists() else tree / "feeds.conf.default"
    lines = original.read_text().splitlines()
    lines = [line for line in lines if not re.match(r"^src-\S+\s+vantage\s", line)]
    feeds.write_text("\n".join(lines + [VANTAGE_FEED]) + "\n")

    mirrors_path = tree / "scripts/projectsmirrors.json"
    mirrors = json.loads(mirrors_path.read_text())
    for project, urls in PROJECT_MIRRORS.items():
        if project not in mirrors:
            raise ValueError(f"Unsupported source mirror layout: missing {project}")
        mirrors[project] = urls
    mirrors_path.write_text(json.dumps(mirrors, indent=2) + "\n")

    libressl = tree / "tools/libressl/Makefile"
    contents, count = re.subn(
        r"^PKG_SOURCE_URL:=[^\n]*(?:\n[ \t]+[^\n]*)*",
        "PKG_SOURCE_URL:=https://ftp.openbsd.org/pub/OpenBSD/LibreSSL",
        libressl.read_text(),
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("Unsupported LibreSSL source URL definition")
    libressl.write_text(contents)

    # The downloader also prepends proxies outside projectsmirrors.json.
    downloader = tree / "scripts/download.pl"
    contents = downloader.read_text()
    start = "\t} elsif ($mirror =~ /^\\@GITHUB\\/(.+)$/) {\n"
    end = "\t} elsif ($mirror =~ /^\\@GNU\\/(.+)$/) {\n"
    try:
        first = contents.index(start) + len(start)
        last = contents.index(end, first)
    except ValueError as error:
        raise ValueError("Unsupported downloader @GITHUB layout") from error
    downloader.write_text(contents[:first] + "\t\tprojectsmirrors '@GITHUB', $1;\n" + contents[last:])

    shutil.copytree(ROOT / "tr3000/files", tree / "files", dirs_exist_ok=True)


def check_config(config):
    selected = set(config.read_text().splitlines())
    for symbol in (
        "TARGET_mediatek_filogic_DEVICE_cudy_tr3000-v1-ubootmod",
        "PACKAGE_luci",
        "PACKAGE_luci-theme-vantage",
        "PACKAGE_luci-i18n-vantage-theme-zh-cn",
    ):
        if f"CONFIG_{symbol}=y" not in selected:
            raise ValueError(f"make defconfig did not retain CONFIG_{symbol}=y")
    if selected & {
        "CONFIG_PACKAGE_default-settings-chn=y",
        "CONFIG_PACKAGE_default-settings-chn=m",
    }:
        raise ValueError("China-specific default settings must remain disabled")


def configure(tree, ccache=False):
    prepare_source(tree)
    for action in ("update", "install"):
        subprocess.run(["./scripts/feeds", action, "-a"], cwd=tree, check=True)
    config = tree / ".config"
    shutil.copyfile(ROOT / "tr3000/seed.config", config)
    if ccache:
        with config.open("a") as output:
            output.write("\nCONFIG_CCACHE=y\n")
    subprocess.run(["make", "defconfig"], cwd=tree, check=True)
    check_config(config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path, nargs="?", default=ROOT / "immortalwrt")
    parser.add_argument("--ccache", action="store_true", help="enable CI's ccache")
    args = parser.parse_args()
    try:
        configure(args.tree.resolve(), args.ccache)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Configuration failed: {error}\n")


if __name__ == "__main__":
    main()
