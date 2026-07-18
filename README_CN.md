# ImmortalWrt 固件构建器

[![ImmortalWrt Builder](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml/badge.svg?branch=main)](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml)
[![Latest Release](https://img.shields.io/github/v/release/coachpo/immortalwrt-firmware-builder?sort=semver&style=flat-square&label=Release&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)
[![Downloads (latest)](https://img.shields.io/github/downloads/coachpo/immortalwrt-firmware-builder/latest/total?style=flat-square&label=Downloads&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)

[English](README.md) | 简体中文

用于构建并（可选）发布 Cudy TR3000 和小米 CR6606 的 ImmortalWrt 固件的种子配置与 GitHub Actions 工作流。CI 会在运行时把 `immortalwrt/immortalwrt` 检出到已忽略的 `immortalwrt/` 目录。

- Cudy TR3000 (Filogic)
- Xiaomi CR6606 (MT7621)

每个 `seed.config` 都用于复制到源码树根目录，通过 `make defconfig` 展开为完整的 `.config`。在编译前，你也可以通过 `make menuconfig` 进行交互式调整。

## 仓库结构
- `tr3000/seed.config` — TR3000 功能更完整的配置。
- `cr6606/seed.config` — CR6606 轻量配置。
- `immortalwrt/` — 已忽略的运行时源码检出目录，由本地命令或 CI 填充。
- `.github/workflows/build-firmware.yml` — 拉取 ImmortalWrt、构建、缓存并发布固件。
- `.github/workflows/cleanup-runs-releases.yml` — 定期清理旧 workflow runs 与兼容的 `immortalwrt-*` Releases。

## 快速开始
方式 A：在本仓库中把 ImmortalWrt 克隆到已忽略的运行时目录：

```bash
git clone https://github.com/coachpo/immortalwrt-firmware-builder.git
cd immortalwrt-firmware-builder
git clone --depth=1 https://github.com/immortalwrt/immortalwrt.git immortalwrt
# 可选：与 CI 的 immortalwrt_ref 输入一致，切换到指定分支、标签或 SHA
# git -C immortalwrt fetch --depth=1 origin <branch-tag-or-sha>
# git -C immortalwrt checkout --detach FETCH_HEAD

cd immortalwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cp ../tr3000/seed.config .config    # TR3000 功能更全面
# 或
cp ../cr6606/seed.config .config    # CR6606 轻量
make defconfig
make menuconfig    # 可选
make -j"$(nproc)" V=sc
```

方式 B：在你自己的 ImmortalWrt（或 OpenWrt）源码树根目录使用种子配置：

```bash
cp /path/to/immortalwrt-firmware-builder/tr3000/seed.config .config    # TR3000 功能更全面
# 或
cp /path/to/immortalwrt-firmware-builder/cr6606/seed.config .config    # CR6606 轻量
make defconfig
make menuconfig    # 可选
make -j"$(nproc)" V=sc
```

编译完成后的固件镜像会生成在 `bin/targets/<target>/<subtarget>/` 目录下。

## GitHub Actions（workflow_dispatch）
工作流：**Build ImmortalWrt firmware**（`.github/workflows/build-firmware.yml`）。

输入：
- `immortalwrt_ref`：可选的 `immortalwrt/immortalwrt` 分支、标签或 SHA；留空时使用上游默认分支，或仓库变量 `IMMORTALWRT_REF`。
- `cache_epoch`：可选缓存命名空间；留空时使用仓库变量 `CACHE_EPOCH` 或 `v1`。

行为：
- 以 `submodules: false` 检出本仓库，然后在运行时把 `immortalwrt/immortalwrt` 检出到 `immortalwrt/`。
- 使用现有 `cr6606/seed.config` 与 `tr3000/seed.config` 分别构建两个机型，并保留 `immortalwrt-*` Release 标签前缀兼容性。
- 分离 `ccache` 与 `dl` 缓存，按机型、ImmortalWrt ref、seed hash 与 cache epoch 生成 key。
- GitHub 缓存创建后不可原地修改。需要刷新时，修改 `cache_epoch` 输入或仓库变量 `CACHE_EPOCH`；工作流会从旧匹配缓存恢复，再保存到新的命名空间。
- 成功后上传 7 天保留的构建产物，并发布包含固件和 manifest 的 Release。

清理工作流：**Cleanup workflow runs and releases**（`.github/workflows/cleanup-runs-releases.yml`）会定期清理旧 workflow runs 与兼容的 `immortalwrt-*` Releases。

## 启用的包与功能对比

下表对比了两个种子配置启用的功能。

| CR6606 | TR3000 | 功能 | 用途 | 备注 |
| --- | --- | --- | --- | --- |
| ✅ | ✅ | LuCI Web UI + 主题 | 通过主题（Bootstrap/Argon + 中文界面）进行 Web 管理 | |
| ✅ | ✅ | Web 服务器（LuCI） | 使用 uHTTPd 提供 LuCI 服务 | |
| ✅ | ✅ | 无线 | Wi‑Fi 6 支持（MT7915E 驱动、regdb）与 WPA2/3（wpad-openssl） | |
| ✅ | ✅ | QoS（基于 nftables） | 使用 nft-qos 的简单带宽/QoS 管理（+ 中文界面） | |
| ✅ | ✅ | 诊断 | 基础排障工具（iperf3、tcpdump、htop） | |
| ✅ | ✅ | Web 终端 | 浏览器内 Shell（ttyd，含中文界面） | |
| ✅ | ✅ | 本地发现 | mDNS/Bonjour 与名称解析（Avahi、nss-mdns） | |
| ✅ | ✅ | UPnP IGD | 自动端口转发（miniupnpd-nftables + 中文界面） | |
| ✅ | ✅ | 通过 Cloudflared 的 DoH | DNS over HTTPS 隧道，含 LuCI UI（中文） | |
| ✅ | ✅ | HTTPS DNS Proxy | 轻量级 DoH 客户端，含 LuCI UI（中文） | |
| ✅ | ✅ | 广告拦截 | 基于 DNS 的广告/恶意域名拦截（中文界面） | |
| ✅ | ✅ | DNS/DHCP 后端 | 功能完整的 dnsmasq（DNSSEC、DHCPv6、TFTP、权威） | |
| ✅ | ✅ | TLS/加密 | OpenSSL TLS 后端（curl/wget-ssl），系统级 OpenSSL 配置 | |
| ✅ | ✅ | IPv6 支持 | DHCPv6 与 IPv6 DHCP 服务（odhcp6c、odhcpd） | |
| ✅ | ✅ | 防火墙 | 基于 nftables 的 firewall4 | |
| ✅ | ✅ | CA 证书 | 根证书集合用于 TLS 校验 | |
| ✅ | ✅ | 软件包管理器 UI | 在 LuCI 中管理软件包（中文界面） | |
| ✅ | ✅ | 网络工具 | socat 及其 LuCI 界面（中文） | |
| ✅ | ✅ | 高级网络工具 | 丰富的网络工具（curl、wget、arping 等） | |
| ✅ | ✅ | 编辑器（vim） | 功能完善的命令行编辑器 | |
| ❌ | ✅ | 文件共享 | Samba4 服务器（含 Avahi、NetBIOS、VFS、WSDD2 + 中文界面） | CR6606 无 USB 接口 |
| ❌ | ✅ | USB 打印 | 打印服务器（p910nd JetDirect）及 LuCI UI（中文） | CR6606 无 USB 接口 |
| ❌ | ✅ | 磁盘管理 | LuCI 磁盘管理（Btrfs、NTFS3 支持 + 中文界面） | CR6606 无 USB 接口 |
| ❌ | ✅ | 存储与文件系统 | 完整的文件系统支持（ext4、Btrfs、exFAT、NTFS3） | CR6606 无 USB 接口 |
| ❌ | ✅ | USB 网络 | 广泛的 USB 转以太网适配器支持 | CR6606 无 USB 接口 |
| ❌ | ✅ | USB 工具 | USB 工具与设备识别 | CR6606 无 USB 接口 |
| ❌ | ✅ | 文件管理器 | LuCI Web 文件管理器（中文界面） | CR6606 无 USB 接口 |


## 许可证

本项目使用 MIT 许可证 - 详情见 [LICENSE](LICENSE) 文件。


