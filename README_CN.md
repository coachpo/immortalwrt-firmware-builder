# ImmortalWrt 固件构建器

[![ImmortalWrt Builder](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml/badge.svg?branch=main)](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml)
[![Latest Release](https://img.shields.io/github/v/release/coachpo/immortalwrt-firmware-builder?sort=date&style=flat-square&label=Release&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)
[![Downloads (latest)](https://img.shields.io/github/downloads/coachpo/immortalwrt-firmware-builder/latest/total?style=flat-square&label=Downloads&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)

[English](README.md) | 简体中文

用于构建 **Cudy TR3000 v1（MediaTek Filogic，OpenWrt U-Boot 布局）** ImmortalWrt 固件的种子配置与自动化工作流。所选设备配置为 `cudy_tr3000-v1-ubootmod`，对应[上游设备定义](https://github.com/immortalwrt/immortalwrt/blob/master/target/linux/mediatek/image/filogic.mk)。请使用与硬件版本及引导布局匹配的镜像。

[种子配置](tr3000/seed.config) 用于复制到源码树根目录，通过 `make defconfig` 展开为完整的 `.config`，也可通过 `make menuconfig` 调整。配置选择了 LuCI、VPN 工具、DoH、QoS 及 USB 网络共享和调制解调器相关软件包。最终软件包和设备默认配置取决于所选 ImmortalWrt 源码与 feeds，可查看生成的 `.config` 和固件 `.manifest` 确认。

## 仓库结构

- `tr3000/seed.config` — TR3000 v1 U-Boot 布局配置。
- `immortalwrt/` — 已忽略的运行时源码检出目录，由本地命令或 CI 填充。
- `Dockerfile` — Ubuntu 22.04 构建环境，使用非 root 的 `builder` 用户运行。
- `.github/workflows/build-firmware.yml` — 手动触发的源码拉取、构建、缓存及 Release 发布工作流。
- `.github/workflows/cleanup-runs-releases.yml` — 定期清理工作流运行记录与 `immortalwrt-*` Releases。

## 主机构建依赖

以下依赖列表与 Dockerfile 的 Ubuntu 22.04 环境一致，适用于 x86-64 Linux 主机。其他 Ubuntu/Debian 版本的软件包可用性可能不同。编译固件时请使用非 root 用户。

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

## 快速开始

方式 A：在本仓库中把 ImmortalWrt 克隆到已忽略的运行时目录：

```bash
git clone https://github.com/coachpo/immortalwrt-firmware-builder.git
cd immortalwrt-firmware-builder
git clone --depth=1 --recurse-submodules https://github.com/immortalwrt/immortalwrt.git immortalwrt
# 可选：与 CI 的 immortalwrt_ref 输入一致，切换到指定分支、标签或 SHA
# git -C immortalwrt fetch --depth=1 origin <branch-tag-or-sha>
# git -C immortalwrt checkout --detach FETCH_HEAD
# git -C immortalwrt submodule update --init --recursive

cd immortalwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cp ../tr3000/seed.config .config
make defconfig
make menuconfig    # 可选调整
make -j"$(nproc)" V=sc
```

方式 B：在已有的 ImmortalWrt 源码树根目录执行：

```bash
./scripts/feeds update -a && ./scripts/feeds install -a
cp /path/to/immortalwrt-firmware-builder/tr3000/seed.config .config
make defconfig
make menuconfig    # 可选调整
make -j"$(nproc)" V=sc
```

源码与 feeds 必须包含所选设备配置及软件包。种子配置包含 ImmortalWrt 特有的软件包，不能保证在 OpenWrt 源码树中直接使用。

固件镜像与 manifest 生成在 ImmortalWrt 源码树的 `bin/targets/mediatek/filogic/` 目录下。

## GitHub Actions（workflow_dispatch）

打开 **Actions → Build ImmortalWrt firmware → Run workflow** 手动运行。仅推送代码不会触发固件构建。构建任务成功后自动执行 Release 发布任务，没有可选发布开关。

输入与回退优先级：

- `immortalwrt_ref`：非空工作流输入 → 仓库变量 `IMMORTALWRT_REF` → 上游默认分支。支持分支、标签或 commit SHA。
- `cache_epoch`：非空工作流输入 → 仓库变量 `CACHE_EPOCH` → `v1`。

行为：

- 检出本仓库，然后将 `immortalwrt/immortalwrt` 检出到 `immortalwrt/`，递归检出子模块。
- CI 使用 `ubuntu-latest`，Dockerfile 使用 Ubuntu 22.04，两者是独立的构建环境。
- 更新并安装 feeds，复制 `tr3000/seed.config`，启用 `CONFIG_CCACHE=y`，执行 `make defconfig`。
- 使用所有可用 CPU 线程编译；并行编译失败时，用 `make -j1 V=s` 重试。
- ccache 容量上限为 4 GB。独立的 `ccache` 与 `dl` 缓存 key 包含 runner 操作系统、`tr3000`、源码 ref、seed hash 和 cache epoch。
- 将 `cache_epoch` 改为新值会生成新的缓存 key，但恢复前缀仍可能匹配并复用旧缓存。这会刷新缓存命名空间，并不保证从空缓存开始。
- 以 `immortalwrt_firmware_tr3000_<YYYYMMDDHHMM>` 为名上传选定的固件文件，保留 7 天；随后发布 `immortalwrt-<ref-or-default>-build<run-number>-<YYYYMMDD-HHMM>` 标签的 Release。不支持的标签字符会替换为下划线。

产物收集步骤预期在 `immortalwrt/bin/targets/mediatek/filogic/` 下找到以下文件：

```text
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-bl31-uboot.fip
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-initramfs-recovery.itb
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-preloader.bin
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-squashfs-sysupgrade.itb
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod.manifest
```

工作流中的路径是固定的。如果所选源码 ref 改变了输出文件命名，需要同步调整产物收集路径和 Release 文件匹配规则。

清理工作流每天 03:00 UTC 运行，也可手动触发。它删除已完成且结果为 `action_required`、`cancelled`、`failure` 或 `skipped` 的运行记录，为每个工作流保留最近 10 次成功运行。清理 action 还会删除已删除工作流的孤立运行记录。Release 清理会保留最新的 10 个标签以 `immortalwrt-` 开头的非草稿 Release，删除更早匹配的 Release 及对应标签。

## Docker 构建环境

在 x86-64 Linux 主机上，从本仓库根目录执行以下命令。通过构建参数匹配当前用户的 UID/GID，使容器能够写入挂载的源码目录：

```bash
docker build \
  --build-arg USER_UID="$(id -u)" \
  --build-arg USER_GID="$(id -g)" \
  -t immortalwrt-builder .
```

省略构建参数时，Dockerfile 默认使用 UID 1001、GID 121。请使用非 root 的 UID，并确保 UID 与 GID 在基础镜像中均未被占用。

如果尚无 `immortalwrt/` 目录，先克隆源码，再从构建器仓库根目录启动容器：

```bash
git clone --depth=1 --recurse-submodules https://github.com/immortalwrt/immortalwrt.git immortalwrt

docker run --rm -it \
  -v "$(pwd)":/workdir \
  immortalwrt-builder bash
# 容器内执行：
cd /workdir/immortalwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cp ../tr3000/seed.config .config
make defconfig && make -j"$(nproc)" V=sc
```

Dockerfile 提供统一的构建环境，但基础镜像、apt 软件包版本没有固定，默认源码及 feeds 也可能变化，因此不保证固件二进制可复现。

## 种子配置显式选择的软件包

以下软件包由 `tr3000/seed.config` 显式选择。设备默认软件包及依赖通过 `make defconfig` 解析。

| 功能 | 选择的软件包 |
| --- | --- |
| LuCI 与 Argon 主题 | `luci`, `luci-theme-argon`, `luci-app-argon-config`, `luci-i18n-base-zh-cn`, `luci-i18n-argon-config-zh-cn` |
| Web 管理服务 | `rpcd`, `uhttpd`, `uhttpd-mod-ubus` |
| CA 证书 | `ca-certificates` |
| QoS | `nft-qos`, `luci-app-nft-qos`, `luci-i18n-nft-qos-zh-cn` |
| 诊断工具 | `htop`, `iperf3`, `tcpdump-mini` |
| DNS over HTTPS | `https-dns-proxy`, `luci-app-https-dns-proxy`, `luci-i18n-https-dns-proxy-zh-cn` |
| DNS/DHCP | `dnsmasq-full` |
| 防火墙界面 | `luci-app-firewall`, `luci-i18n-firewall-zh-cn` |
| WireGuard VPN | `wireguard-tools`, `kmod-wireguard`, `luci-proto-wireguard`, `luci-i18n-wireguard-zh-cn` |
| OpenVPN（mbedTLS） | `openvpn-mbedtls`, `luci-proto-openvpn` |
| Tailscale | `tailscale`, `luci-app-tailscale-community` |
| UPnP | `miniupnpd-nftables`, `luci-app-upnp`, `luci-i18n-upnp-zh-cn` |
| USB 网络共享 | `kmod-usb-net-rndis`, `kmod-usb-net-cdc-ncm` |
| USB 蜂窝调制解调器 | `usb-modeswitch`, `uqmi`, `umbim`, `ppp`, `comgt`, `kmod-usb-serial-option`, `kmod-usb-acm` |
| 时区数据 | `zoneinfo-core`, `zoneinfo-europe` |

种子配置通过 `CONFIG_LUCI_LANG_zh_Hans=y` 启用 LuCI 简体中文翻译，并显式取消选择 `default-settings-chn`。

## 故障排查

- 缺少软件包时，重新执行 `./scripts/feeds update -a && ./scripts/feeds install -a`，并确认所选源码与 feeds 包含种子配置引用的软件包符号。
- 编译失败时，尝试单线程详细输出：`make -j1 V=s`。
- 重试大型构建前检查磁盘空间；编译输出、中间文件和下载的源码会占用较多空间。
- 上传产物时找不到文件，应对照实际文件名检查工作流的固定收集路径。
- 需要刷新 CI 缓存快照时，使用新的 `cache_epoch` 值。工作流仍可能通过回退前缀恢复旧缓存内容。

## 许可证

本项目使用 MIT 许可证，详情见 [LICENSE](LICENSE)。
