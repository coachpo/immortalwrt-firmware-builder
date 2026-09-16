# ImmortalWrt Firmware Builder

[![ImmortalWrt Builder](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml/badge.svg?branch=main)](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml)
[![Latest Release](https://img.shields.io/github/v/release/coachpo/immortalwrt-firmware-builder?sort=date&style=flat-square&label=Release&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)
[![Downloads (latest)](https://img.shields.io/github/downloads/coachpo/immortalwrt-firmware-builder/latest/total?style=flat-square&label=Downloads&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)

English | [简体中文](README_CN.md)

Firmware seed and build automation for **Cudy TR3000 v1 (MediaTek Filogic, OpenWrt U-Boot layout)**. The selected device profile is `cudy_tr3000-v1-ubootmod`, as defined in the [upstream device definitions](https://github.com/immortalwrt/immortalwrt/blob/master/target/linux/mediatek/image/filogic.mk). Use images for this hardware revision and bootloader layout.

The [seed configuration](tr3000/seed.config) is a starting `.config` to expand with `make defconfig`, then optionally refine with `make menuconfig`. It selects LuCI, VPN tools, DoH, QoS, and USB tethering/modem packages. Final packages and device defaults depend on the selected ImmortalWrt source and feeds; inspect the generated `.config` and firmware `.manifest` to confirm the result.

## Repository Layout

- `tr3000/seed.config` — TR3000 v1 U-Boot layout configuration.
- `immortalwrt/` — ignored runtime checkout location for ImmortalWrt, populated by local commands or CI.
- `Dockerfile` — Ubuntu 22.04 build environment, running as the non-root `builder` user.
- `.github/workflows/build-firmware.yml` — manually triggered workflow to fetch ImmortalWrt, build, cache, and publish a release.
- `.github/workflows/cleanup-runs-releases.yml` — scheduled cleanup of workflow runs and `immortalwrt-*` releases.

## Prerequisites (host build)

The dependency list below matches the Dockerfile's Ubuntu 22.04 environment and assumes an x86-64 Linux host. Package availability may differ on other Ubuntu/Debian releases. Run the firmware build as a non-root user.

```bash
sudo apt-get update && sudo apt-get install -y \
  ack antlr3 asciidoc autoconf automake autopoint binutils gcc-multilib gettext flex gawk \
  bison build-essential bzip2 ccache clang cmake cpio curl device-tree-compiler ecj fastjar \
  g++-multilib git libgnutls28-dev gperf haveged help2man intltool lib32gcc-s1 libc6-dev-i386 libelf-dev \
  libglib2.0-dev libgmp-dev libltdl-dev libmpc-dev libmpfr-dev libncurses-dev libpython3-dev \
  libreadline-dev libssl-dev libtool libyaml-dev lld llvm lrzsz genisoimage msmtp nano ninja-build \
  p7zip p7zip-full patch pkgconf python3 python3-pip python3-ply python3-docutils python3-pyelftools \
  qemu-utils re2c rsync scons squashfs-tools subversion swig texinfo uglifyjs upx-ucl unzip vim wget \
  xmlto xxd zlib1g-dev zstd
```

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

cd immortalwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cp ../tr3000/seed.config .config
make defconfig
make menuconfig    # optional tweaks
make -j"$(nproc)" V=sc
```

Option B — use an existing ImmortalWrt source tree. From its root directory:

```bash
./scripts/feeds update -a && ./scripts/feeds install -a
cp /path/to/immortalwrt-firmware-builder/tr3000/seed.config .config
make defconfig
make menuconfig    # optional tweaks
make -j"$(nproc)" V=sc
```

The source and feeds must provide the selected device profile and packages. This seed includes ImmortalWrt-specific packages and is not guaranteed to work unchanged in an OpenWrt tree.

Firmware images and manifests land under `bin/targets/mediatek/filogic/` within the ImmortalWrt tree.

## GitHub Actions (workflow_dispatch)

Open **Actions → Build ImmortalWrt firmware → Run workflow**. A push alone does not trigger a firmware build. Once the build job succeeds, the release job runs automatically; there is no publish toggle.

Inputs and fallback order:

- `immortalwrt_ref`: non-empty workflow input → repository variable `IMMORTALWRT_REF` → upstream default branch. Accepts a branch, tag, or commit SHA.
- `cache_epoch`: non-empty workflow input → repository variable `CACHE_EPOCH` → `v1`.

Behavior:

- Checks out this repository, then checks out `immortalwrt/immortalwrt` into `immortalwrt/` with recursive submodules.
- Builds on `ubuntu-latest`, while the Dockerfile uses Ubuntu 22.04; these are separate build environments.
- Updates and installs feeds, copies `tr3000/seed.config`, enables `CONFIG_CCACHE=y`, and runs `make defconfig`.
- Builds with all available CPU threads, retrying with `make -j1 V=s` if the parallel build fails.
- Uses a 4 GB ccache limit. Separate `ccache` and `dl` keys contain runner OS, `tr3000`, source ref, seed hash, and cache epoch.
- Changing `cache_epoch` to a new value creates a new cache key, but restore prefixes can still reuse an older matching cache. This refreshes the cache namespace; it does not guarantee an empty cache.
- Uploads the selected firmware files as `immortalwrt_firmware_tr3000_<YYYYMMDDHHMM>` with 7-day retention, then publishes an `immortalwrt-<ref-or-default>-build<run-number>-<YYYYMMDD-HHMM>` release tag. Unsupported tag characters are replaced with underscores.

The collection step expects these files under `immortalwrt/bin/targets/mediatek/filogic/`:

```text
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-bl31-uboot.fip
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-initramfs-recovery.itb
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-preloader.bin
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-squashfs-sysupgrade.itb
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod.manifest
```

The paths are fixed in the workflow. If a selected source ref changes output naming, adjust the collection and release file patterns to match that ref.

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
cd /workdir/immortalwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cp ../tr3000/seed.config .config
make defconfig && make -j"$(nproc)" V=sc
```

The Dockerfile provides a shared build environment, but its base image and apt packages are not pinned, and the default source/feeds can change. It does not guarantee reproducible firmware binaries.

## Explicit Seed Selections

These are the packages explicitly selected in `tr3000/seed.config`. Device defaults and dependencies are resolved by `make defconfig`.

| Feature | Selected packages |
| --- | --- |
| LuCI and Argon theme | `luci`, `luci-theme-argon`, `luci-app-argon-config`, `luci-i18n-base-zh-cn`, `luci-i18n-argon-config-zh-cn` |
| Web management services | `rpcd`, `uhttpd`, `uhttpd-mod-ubus` |
| CA certificates | `ca-certificates` |
| QoS | `nft-qos`, `luci-app-nft-qos`, `luci-i18n-nft-qos-zh-cn` |
| Diagnostics | `htop`, `iperf3`, `tcpdump-mini` |
| DNS over HTTPS | `https-dns-proxy`, `luci-app-https-dns-proxy`, `luci-i18n-https-dns-proxy-zh-cn` |
| DNS/DHCP | `dnsmasq-full` |
| Firewall UI | `luci-app-firewall`, `luci-i18n-firewall-zh-cn` |
| WireGuard VPN | `wireguard-tools`, `kmod-wireguard`, `luci-proto-wireguard`, `luci-i18n-wireguard-zh-cn` |
| OpenVPN (mbedTLS) | `openvpn-mbedtls`, `luci-proto-openvpn` |
| Tailscale | `tailscale`, `luci-app-tailscale-community` |
| UPnP | `miniupnpd-nftables`, `luci-app-upnp`, `luci-i18n-upnp-zh-cn` |
| USB tethering | `kmod-usb-net-rndis`, `kmod-usb-net-cdc-ncm` |
| USB cellular modems | `usb-modeswitch`, `uqmi`, `umbim`, `ppp`, `comgt`, `kmod-usb-serial-option`, `kmod-usb-acm` |
| Timezone data | `zoneinfo-core`, `zoneinfo-europe` |

The seed enables Simplified Chinese LuCI translations with `CONFIG_LUCI_LANG_zh_Hans=y` and explicitly deselects `default-settings-chn`.

## Troubleshooting

- Re-run feeds if packages are missing: `./scripts/feeds update -a && ./scripts/feeds install -a`. Confirm the selected source and feeds contain the package symbols requested by the seed.
- For build failures, try a single-thread verbose build: `make -j1 V=s`.
- Check free disk space before retrying large builds; build output, staging files, and downloaded sources consume substantial space.
- If artifact upload finds no files, compare the generated filenames with the workflow's fixed collection paths.
- To refresh CI cache snapshots, use a new `cache_epoch` value. Older cache contents may still be restored through the fallback prefixes.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE).
