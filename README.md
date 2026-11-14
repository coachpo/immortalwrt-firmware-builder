# ImmortalWrt Firmware Builder

[![ImmortalWrt Builder](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml/badge.svg?branch=main)](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml)
[![Latest Release](https://img.shields.io/github/v/release/coachpo/immortalwrt-firmware-builder?sort=date&style=flat-square&label=Release&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)
[![Downloads (latest)](https://img.shields.io/github/downloads/coachpo/immortalwrt-firmware-builder/latest/total?style=flat-square&label=Downloads&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)

English | [简体中文](README_CN.md)

[Build](#quick-start-local-build) · [Configuration](#configuration-and-defaults) · [Contributing](#development-and-validation) · [Agent guide](AGENTS.md)

Firmware seed and build automation for **Cudy TR3000 v1 (MediaTek Filogic, OpenWrt U-Boot layout)**. The selected device profile is `cudy_tr3000-v1-ubootmod`, as defined in the [upstream device definitions](https://github.com/immortalwrt/immortalwrt/blob/master/target/linux/mediatek/image/filogic.mk). Use images for this hardware revision and bootloader layout.

The shared [configuration helper](scripts/configure.py) prepares feeds and image defaults, then expands the [seed](tr3000/seed.config) with `make defconfig`; optionally refine with `make menuconfig`. It selects LuCI, VPN tools, DoH, QoS, and USB tethering/modem packages. Final packages and device defaults depend on the selected ImmortalWrt source and feeds; inspect the generated `.config` and firmware `.manifest` to confirm the result.

## Repository Layout

- `tr3000/seed.config` — authoritative target and package seed.
- `tr3000/files/` — image overlay, including late default-theme selection.
- `scripts/configure.py` — shared local/CI feed, neutral source mirror, overlay and configuration preparation.
- `scripts/ci.py` — cache keys, complete firmware staging and build provenance.
- `tests/test_configure.py` — targeted configuration and shell-control-flow tests.
- `tests/test_ci.py` — targeted artifact, cache and provenance tests; uses Git locally without new commits or network access.
- `immortalwrt/` — ignored runtime checkout location for ImmortalWrt, populated by local commands or CI.
- `Dockerfile` — Ubuntu 22.04 build environment, running as the non-root `builder` user.
- `.github/workflows/build-firmware.yml` — manually triggered workflow to fetch ImmortalWrt, build, cache, and publish a release.
- `.github/workflows/quick-checks.yml` — independent checks on pushes, pull requests and manual dispatch; never builds or releases firmware.
- `.github/workflows/cleanup-runs-releases.yml` — scheduled cleanup of workflow runs and `immortalwrt-*` releases.

## Prerequisites (host build)

Use an x86-64 Linux host, a case-sensitive filesystem and a non-root build user. The Ubuntu 22.04 dependency list is maintained in the [Dockerfile](Dockerfile) (`apt-get install`); install those packages on a matching host or use the container below. Firmware CI installs dependencies separately on `ubuntu-latest` (currently Ubuntu 26.04), not in the Docker image.

## Quick Start (local build)

Option A — clone ImmortalWrt into this repo's ignored runtime path:

```bash
git clone https://github.com/coachpo/immortalwrt-firmware-builder.git
cd immortalwrt-firmware-builder
git clone --depth=1 --recurse-submodules https://github.com/immortalwrt/immortalwrt.git immortalwrt
# Optional ref override, matching CI's immortalwrt_ref input:
# git -C immortalwrt fetch --depth=1 origin <branch-tag-or-sha>
# git -C immortalwrt checkout --detach FETCH_HEAD
# git -C immortalwrt submodule update --init --recursive

python3 scripts/configure.py immortalwrt
cd immortalwrt
make menuconfig    # optional tweaks
make -j"$(nproc)" V=sc
```

Option B — use an existing source tree. From this builder repository's root, run `python3 scripts/configure.py /path/to/immortalwrt`, then build in that source tree. The helper preserves other feeds and unrelated overlay files, but replaces `.config` with this project's seed and owns the overlay paths supplied here. Do not bypass it by copying only the seed: that omits the theme feed and defaults.

The source and feeds must provide the selected device profile and packages. This seed includes ImmortalWrt-specific packages and is not guaranteed to work unchanged in an OpenWrt tree.

Firmware images and manifests land under `bin/targets/mediatek/filogic/` within the ImmortalWrt tree.

## GitHub Actions (workflow_dispatch)

Open **Actions → Build ImmortalWrt firmware → Run workflow**. A push alone does not trigger a firmware build. Once the build job succeeds, the release job runs automatically; there is no publish toggle.

**Quick checks** runs independently on pushes, pull requests and manual dispatch. It runs the two targeted test files, image-default shell syntax, push/PR event-range whitespace checks (latest-commit checks for manual/new-branch runs) and actionlint 1.7.12 (with ShellCheck when installed). It does not fetch firmware sources/feeds, restore firmware caches, compile or publish. Its result neither starts nor gates the manually dispatched firmware workflow.

Inputs and fallback order:

- `immortalwrt_ref`: non-empty workflow input → repository variable `IMMORTALWRT_REF` → upstream default branch. Accepts a branch, tag, or commit SHA.
- `cache_epoch`: non-empty workflow input → repository variable `CACHE_EPOCH` → `v1`.

Behavior:

- Checks out this repository, then checks out `immortalwrt/immortalwrt` into `immortalwrt/` with recursive submodules.
- Firmware compilation follows `ubuntu-latest` (currently Ubuntu 26.04). Selected ImmortalWrt releases require GNU host tools, so CI selects Ubuntu's official `coreutils-from-gnu` provider instead of the default uutils provider, and verifies GNU `install` before configuration. The [Ubuntu provider-switch documentation](https://ubuntu.com/server/docs/reference/other-tools/sudo-rs/) explains the required `--allow-remove-essential` option; this switches providers only on the disposable runner. No source prerequisites are suppressed with `FORCE=1`. The Dockerfile remains a separate Ubuntu 22.04 build environment.
- Runs `python3 scripts/configure.py immortalwrt --ccache`, reusing local preparation and enabling `CONFIG_CCACHE=y`. The helper checks critical selections after expanding the configuration.
- After feeds update, preparation keeps Go source/bootstrap downloads on official endpoints and applies the [upstream C-bootstrap dialect fix](https://github.com/openwrt/packages/blob/openwrt-24.10/lang/golang/golang/Makefile): only the Go 1.4 C bootstrap uses `-std=gnu17`, so GCC's newer C23 default does not reject its `bool` typedef. The runner, compiler and selected firmware ref are not downgraded; target compiler flags are unchanged.
- Builds with all available CPU threads, retrying with `make -j1 V=s` if the parallel build fails.
- Uses a 4 GB ccache limit. Separate `ccache` and `dl` keys contain runner OS/architecture, `tr3000`, source ref, seed hash, cache epoch, run ID and attempt. Stable restore prefixes reuse the latest matching snapshot; each run attempt saves a new snapshot automatically, including for a moving default branch. Save ccache only after successful compilation; downloads can be saved after successful configuration even if compilation fails.
- `cache_epoch` remains a manual namespace override, not a required refresh step. Fallback prefixes can reuse older epochs, so changing it does not guarantee an empty cache.
- Uploads the selected firmware files as `immortalwrt_firmware_tr3000_<YYYYMMDDHHMM>` with 7-day retention, then publishes an `immortalwrt-<ref-or-default>-build<run-number>-<YYYYMMDD-HHMM>` release tag. Unsupported tag characters are replaced with underscores.

The collection step expects these files under `immortalwrt/bin/targets/mediatek/filogic/`:

```text
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-bl31-uboot.fip
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-initramfs-recovery.itb
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-preloader.bin
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-squashfs-sysupgrade.itb
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod.manifest
```

The five names are defined once in [scripts/ci.py](scripts/ci.py). Both build staging and release staging require every file to exist and be non-empty before copying anything. Firmware staging and provenance recording require fresh destination directories to exclude stale assets. Downloads use explicit artifact IDs to keep firmware separate from provenance. If a selected source ref changes output naming, update that list rather than relaxing the completeness check.

After compilation finishes (or is skipped after configuration failure), available provenance is uploaded separately with 7-day retention. `build-info.json` records actual builder/source/feed commits, modified feed names, source submodules, configuration/build outcomes, requested ref, run and runner details (including hosted image name/version); `seed.config`, `firmware.config` (when available) and `feeds.conf` capture inputs. `source.patch` is included for tracked source customizations; `feed-<name>.patch` captures tracked changes within each modified feed (apply from that feed's root at its recorded commit). A partial config does not prove successful expansion. Before release, required provenance files, successful outcomes and the builder commit are checked; customized source/feed repositories require their non-empty patches. Successful releases retain provenance alongside the five firmware assets and show builder/source commits in the body. The release tag is anchored to the workflow commit, not a branch that may move during compilation. Traceability does not guarantee binary reproducibility.

The cleanup workflow runs daily at 03:00 UTC and can also be started manually. It deletes completed runs with conclusions `action_required`, `cancelled`, `failure`, or `skipped`, and keeps the latest 10 successful runs per workflow. The cleanup action also removes orphaned runs of deleted workflows. Release cleanup keeps the latest 10 non-draft releases whose tags start with `immortalwrt-`, deleting older matching releases and their tags.

## Docker Build Environment

From this repository's root on an x86-64 Linux host, build an image with the current user's UID/GID so the container can write to the mounted source tree:

```bash
docker build \
  --build-arg USER_UID="$(id -u)" \
  --build-arg USER_GID="$(id -g)" \
  -t immortalwrt-builder .
```

The Dockerfile defaults to UID 1001 and GID 121 if the build arguments are omitted. Use a non-root UID and ensure both IDs are unassigned in the base image.

Clone the source if `immortalwrt/` is not already present, then start the container from the builder repository's root:

```bash
git clone --depth=1 --recurse-submodules https://github.com/immortalwrt/immortalwrt.git immortalwrt

docker run --rm -it \
  -v "$(pwd)":/workdir \
  immortalwrt-builder bash
# inside the container:
cd /workdir
python3 scripts/configure.py immortalwrt
cd immortalwrt
make -j"$(nproc)" V=sc
```

The Dockerfile provides a shared build environment, but its base image and apt packages are not pinned, and the default source/feeds can change. It does not guarantee reproducible firmware binaries.

## Configuration and Defaults

The [seed](tr3000/seed.config) owns explicit selections: LuCI, Vantage, Simplified Chinese translations, nftables QoS/firewall/UPnP, diagnostics, DoH with dnsmasq-full, WireGuard/OpenVPN/Tailscale, USB tethering/cellular modem support and timezone data (`zoneinfo-core`, `zoneinfo-europe`). Europe timezone data does not select a local timezone. Source/feeds and device defaults are expanded by `make defconfig`. The helper fails if the target, LuCI, Vantage or its selected translation is dropped, or `default-settings-chn` is enabled.

### Vantage

The [official Vantage feed](https://github.com/anothaDev/luci-theme-vantage) is registered in the runtime `feeds.conf`, pinned in [configure.py](scripts/configure.py) to v1.0.20 commit `0f8d16f2ce25132e6a074575af16468524d2d5dd`. Installation uses the existing `scripts/feeds` mechanism, not binary downloads or an on-device repository. Only `luci-theme-vantage` and `luci-i18n-vantage-theme-zh-cn` are selected; the separate dashboard `luci-app-vantage` is not required or included. The theme depends on `luci-base`, uses ucode templates and disables CSS minification in its own Makefile. See the [official install guide](https://github.com/anothaDev/luci-theme-vantage/blob/0f8d16f2ce25132e6a074575af16468524d2d5dd/docs/INSTALL.md).

The [late first-boot script](tr3000/files/etc/uci-defaults/zzzz-vantage-theme) selects `luci.main.mediaurlbase=/luci-static/vantage` after package defaults. Its first execution also overrides a theme choice retained by sysupgrade; other retained device settings are not migrated. Argon and its configuration UI/translation are no longer explicitly selected. Bootstrap stays because `luci` → `luci-light` actually depends on it; it is not the default.

**Verified build compatibility:** Ubuntu 26.04 + ImmortalWrt `v24.10.2` (source `cee53da5b58c6241eced0ef17956adda5515634b`, pinned LuCI `dbf5de06f1f3989fab244cc22a43deaa1e3b77b2`) + Vantage `v1.0.20` completed a full firmware build and automatic release in [CI run 43634995216](https://github.com/coachpo/immortalwrt-firmware-builder/actions/runs/43634995216), using builder commit `6071d0f`. This result uses the repository's GNU coreutils provider selection and Go C-bootstrap GNU C17 fix described above. The [published release](https://github.com/coachpo/immortalwrt-firmware-builder/releases/tag/immortalwrt-v24.10.2-build7-20261114-2159) includes firmware and provenance attachments; its manifest confirms both the Vantage theme and Simplified Chinese translation are included.

**Runtime remains unverified:** no physical-device flashing/boot or browser testing has been performed. A successful build does not establish device behavior or the theme's rendered appearance and interactions.

**Other refs:** the ref resolves from workflow input, repository variable, then upstream default branch. The repository variable selects `v24.10.2`; local examples without a ref still follow master (`SNAPSHOT`). Earlier inspection of master source `a4ba8240d8a1aaef7e8c6f2d65e841a9bfd2b8c5` and LuCI `ad75cde88e694b511100576bfbe0a280e5efe6ef` confirmed only the ucode theme integration path, not a full build or runtime test. Vantage reports OpenWrt 25.12/24.10 support (limited 24.10 Wi-Fi/add-on coverage), not snapshot testing. Do not extend the verified combination to other refs or environments without validation; unsupported configuration layouts fail rather than introducing compatibility fallbacks without a consumer requirement.

### Region-neutral defaults

| Source | Policy |
| --- | --- |
| `default-settings-chn` | Explicitly disabled and checked after expansion. Prevent its Shanghai/CST-8 timezone, Tencent/Aliyun/NTSC/CN NTP servers and regional package-mirror rewrite from entering the image. |
| Base time/NTP | Keep inspected upstream UTC (`UTC` on 24.10, `GMT0` on snapshot) and `time.apple.com`, `time1.google.com`, `time.cloudflare.com`, `pool.ntp.org`; do not select another country. |
| DNS/DoH | Keep WAN-provided DNS and upstream generic Cloudflare/Google DoH defaults. Provider catalogs are optional choices, not active presets; retain them. |
| Firmware package feeds | Keep official `downloads.immortalwrt.org`; disabling `default-settings-chn` prevents its `mirrors.vsean.net` rewrite. |
| Build source mirrors | Replace Debian/Apache/GNU/kernel/GNOME mirror lists with project-operated endpoints, removing Tencent, Aliyun, Tsinghua, USTC, NJU and ISCAS defaults. GitHub raw downloads use official `raw.githubusercontent.com` directly, without hardcoded downloader proxy/CDN defaults. Use `ftp.openbsd.org` for LibreSSL instead of its Tencent-led list. Retain other project lists and package hashes. |
| Locale/radio regulation | Keep Chinese UI/translations. Do not set a wireless country or alter board/calibration regulatory data; configure the legally correct deployment country on the device. |

These facts concern inspected source/feeds and fresh configuration, not every possible ref, optional package or settings restored by sysupgrade. On ref changes, review generated configuration, selected package defaults and image contents.

The inspected master feeds also lack the seed's existing `nft-qos`/`luci-app-nft-qos` (including its translation) and `luci-i18n-wireguard-zh-cn` packages. These unrelated selections are retained, not silently replaced with another QoS implementation. Do not interpret the seed's requested features as a verified installed-package list on that snapshot.

## Development and Validation

From this builder repository's root, with Python 3, Git, Perl, make and a C compiler supporting C23/C17 modes for the targeted tests, and actionlint (optionally with ShellCheck) for workflow linting:

```bash
python3 -m unittest discover -s tests -p 'test_configure.py' -v
python3 -m unittest discover -s tests -p 'test_ci.py' -v
sh -n tr3000/files/etc/uci-defaults/zzzz-vantage-theme
actionlint
git diff --check
```

The tests use temporary trees and command doubles for preparation idempotency, feed/configuration ordering, critical selections and UCI failure handling. They do not run real `make defconfig`, UCI or LuCI. For actual expansion on a prepared Linux host, run `python3 scripts/configure.py /path/to/immortalwrt` (optionally `--ccache`): it fetches feeds and replaces that tree's `.config`, without compiling firmware. Inspect `.config` and, after a separately requested build, the manifest and clean-boot UI. Full firmware builds are not the default documentation/script check.

Change selections in the seed, preparation in the helper, and image defaults in `tr3000/files/`. Keep both README translations aligned. These configuration/development sections own architecture and contributor policy; do not create duplicate documents just to fill a template.

**Compatibility policy:** backward compatibility is not required. For authorized replacements, update actual callers, configuration, tests and documentation and remove superseded paths in scope. Do not add aliases, conversions, dual paths or legacy fallbacks without an explicit requirement or verified consumer.

**Design principles:** treat uncertain capability/tier/quota as assumptions, choosing the looser supported option rather than speculative limits. Assume legitimate use; add no preemptive abuse controls or worst-case handling beyond accepted requirements. Record what observation would trigger a revisit, preserving established security and operational obligations. Keep files cohesive and navigable; split obstructive responsibilities, not to satisfy arbitrary line limits or create needless abstractions.

## Troubleshooting

- For missing packages, rerun the shared configuration helper, inspect feed errors and `.config`, and confirm the source/feeds provide the seed symbols. A successful clone does not prove package indexing or configuration expansion succeeded.
- For build failures, try a single-thread verbose build: `make -j1 V=s`.
- Check free disk space before retrying large builds; build output, staging files, and downloaded sources consume substantial space.
- If staging reports missing or empty artifacts, compare generated filenames with the required list in `scripts/ci.py`.
- CI refreshes cache snapshots automatically per run attempt; use `cache_epoch` only for a manual namespace change. Older contents may still be restored through fallback prefixes.

## License

This builder is licensed under the MIT License — see [LICENSE](LICENSE). Downloaded firmware components retain their own licenses; Vantage is GPL-3.0-or-later.
