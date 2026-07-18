# ImmortalWrt Firmware Builder

[![ImmortalWrt Builder](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml/badge.svg?branch=main)](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml)
[![Latest Release](https://img.shields.io/github/v/release/coachpo/immortalwrt-firmware-builder?sort=semver&style=flat-square&label=Release&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)
[![Downloads (latest)](https://img.shields.io/github/downloads/coachpo/immortalwrt-firmware-builder/latest/total?style=flat-square&label=Downloads&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)

English | [简体中文](README_CN.md)

Firmware seeds and build automation to produce ImmortalWrt images for two routers:

- **Cudy TR3000 (MediaTek Filogic)** — feature-rich build with USB, storage, and Samba.
- **Xiaomi CR6606 (MT7621)** — leaner build focused on core routing features.

Each `seed.config` is a starting `.config` you expand with `make defconfig`, then optionally refine with `make menuconfig`.

## Repository Layout
- `tr3000/seed.config` — TR3000 feature-rich profile.
- `cr6606/seed.config` — CR6606 lean profile.
- `immortalwrt/` — ignored runtime checkout location for ImmortalWrt, populated by local commands or CI.
- `Dockerfile` — Reproducible Ubuntu 22.04 build environment with all toolchain deps.
- `.github/workflows/build-firmware.yml` — GitHub Actions workflow to fetch ImmortalWrt, build, cache, and release images.
- `.github/workflows/cleanup-runs-releases.yml` — scheduled cleanup for old workflow runs and compatible `immortalwrt-*` releases.

## Prerequisites (host build)
Ubuntu/Debian build deps match the `Dockerfile`. Minimal one-liner:
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
git clone --depth=1 https://github.com/immortalwrt/immortalwrt.git immortalwrt
# Optional ref override, matching CI's immortalwrt_ref input:
# git -C immortalwrt fetch --depth=1 origin <branch-tag-or-sha>
# git -C immortalwrt checkout --detach FETCH_HEAD

cd immortalwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cp ../tr3000/seed.config .config   # or ../cr6606/seed.config
make defconfig
make menuconfig    # optional tweaks
make -j"$(nproc)" V=sc
```

Option B — drop a seed into your own ImmortalWrt/OpenWrt tree:
```bash
cp /path/to/immortalwrt-firmware-builder/tr3000/seed.config .config   # or cr6606/seed.config
make defconfig
make menuconfig   # optional
make -j"$(nproc)" V=sc
```

Firmware images land under `bin/targets/<target>/<subtarget>/`.

## GitHub Actions (workflow_dispatch)
Workflow: **Build ImmortalWrt firmware** (`.github/workflows/build-firmware.yml`).

Inputs:
- `immortalwrt_ref`: optional branch/tag/SHA for `immortalwrt/immortalwrt`; empty uses the upstream default branch or repository variable `IMMORTALWRT_REF`.
- `cache_epoch`: optional cache namespace; empty uses repository variable `CACHE_EPOCH` or `v1`.

Behavior:
- Checks out this repo with `submodules: false`, then checks out `immortalwrt/immortalwrt` into `immortalwrt/` at runtime.
- Builds both `cr6606` and `tr3000` from the existing `matrix.model/seed.config`, forces `CONFIG_CCACHE=y`, runs `make defconfig`, then builds.
- Restores separate `ccache` and `dl` caches keyed by model, ImmortalWrt ref, seed hash, and cache epoch.
- GitHub caches are immutable. To refresh them, change `cache_epoch` (or repo variable `CACHE_EPOCH`); the workflow restores the nearest older matching cache and saves a fresh cache under the new namespace.
- Uploads artifacts per model (7-day retention) and, on success, publishes an `immortalwrt-*` release tag with binaries and manifests.

Cleanup workflow: **Cleanup workflow runs and releases** (`.github/workflows/cleanup-runs-releases.yml`) keeps old workflow runs and compatible `immortalwrt-*` releases pruned.

## Docker (reproducible build env)
Build the image:
```bash
docker build -t immortalwrt-builder .
```
Run with the repo mounted after cloning ImmortalWrt into the ignored runtime path:
```bash
git clone --depth=1 https://github.com/immortalwrt/immortalwrt.git immortalwrt

docker run --rm -it \
  -v "$(pwd)":/workdir \
  immortalwrt-builder bash
# inside the container:
cd /workdir/immortalwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cp ../tr3000/seed.config .config   # or ../cr6606/seed.config
make defconfig && make -j"$(nproc)" V=sc
```

## Seed Feature Comparison
This table compares the features enabled by both seed configurations.

| CR6606 | TR3000 | Feature | Purpose | Notes |
| --- | --- | --- | --- | --- |
| ✅ | ✅ | LuCI Web UI + themes | Web management with themes (Bootstrap/Argon + Chinese UI) | |
| ✅ | ✅ | Web server (LuCI) | Serves LuCI over HTTP with uHTTPd | |
| ✅ | ✅ | Wireless | Wi-Fi 6 support with MT7915E driver, regulatory database (wireless-regdb), and WPA2/3 (wpad-openssl) | |
| ✅ | ✅ | QoS (nftables) | Simple bandwidth/QoS rules with nft-qos + Chinese UI | |
| ✅ | ✅ | Diagnostics | Basic troubleshooting tools (iperf3, tcpdump, htop) | |
| ✅ | ✅ | Web terminal | Shell access in browser (ttyd) + Chinese UI | |
| ✅ | ✅ | Local discovery | mDNS/Bonjour and name resolution (Avahi, nss-mdns) | |
| ✅ | ✅ | UPnP IGD | Auto port forwarding (miniupnpd-nftables) + Chinese UI | |
| ✅ | ✅ | DoH via Cloudflared | DNS over HTTPS tunnel with LuCI UI + Chinese UI | |
| ✅ | ✅ | HTTPS DNS Proxy | Lightweight DoH client with LuCI UI + Chinese UI | |
| ✅ | ✅ | Adblock | DNS-based ad/malware blocking + Chinese UI | |
| ✅ | ✅ | DNS/DHCP backend | Full-featured dnsmasq (DNSSEC, DHCPv6, TFTP, auth) | |
| ✅ | ✅ | TLS/crypto | OpenSSL TLS backend (curl/wget-ssl) with system OpenSSL config | |
| ✅ | ✅ | IPv6 support | DHCPv6 and IPv6 DHCP services (odhcp6c, odhcpd) | |
| ✅ | ✅ | Firewall | nftables-based firewall4 | |
| ✅ | ✅ | CA certificates | Root certificate bundle for TLS validation | |
| ✅ | ✅ | Package Manager UI | Manage packages in LuCI + Chinese UI | |
| ✅ | ✅ | Network tools | socat with LuCI interface + Chinese UI | |
| ✅ | ✅ | Advanced networking | Extensive networking tools (curl, wget, arping, etc.) | |
| ✅ | ✅ | Editor (vim) | Full-featured CLI editor | |
| ❌ | ✅ | File sharing | Samba4 server with Avahi, NetBIOS, VFS, and WSDD2 + Chinese UI | CR6606 lacks USB ports |
| ❌ | ✅ | USB printing | Print server (p910nd JetDirect) with LuCI UI + Chinese UI | CR6606 lacks USB ports |
| ❌ | ✅ | Disk management | LuCI disk manager with Btrfs, NTFS3 support + Chinese UI | CR6606 lacks USB ports |
| ❌ | ✅ | Storage & filesystems | Full filesystem support (ext4, Btrfs, exFAT, NTFS3) | CR6606 lacks USB ports |
| ❌ | ✅ | USB networking | Extensive USB-to-Ethernet adapter support | CR6606 lacks USB ports |
| ❌ | ✅ | USB tools | USB utilities and device identification | CR6606 lacks USB ports |
| ❌ | ✅ | File manager | Web file manager in LuCI + Chinese UI | CR6606 lacks USB ports |

## Troubleshooting
- Re-run feeds if packages are missing: `./scripts/feeds update -a && ./scripts/feeds install -a`.
- For noisy failures, try a single-thread verbose build: `make -j1 V=s`.
- Free disk space before retrying large builds (`tmp`, `build_dir`, and cached downloads are the biggest users).
- If caches confuse CI, rerun with a new `cache_epoch` input or `CACHE_EPOCH` repository variable value; do not edit seed configs just to rotate caches.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
