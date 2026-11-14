# ImmortalWrt 固件构建器

[![ImmortalWrt Builder](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml/badge.svg?branch=main)](https://github.com/coachpo/immortalwrt-firmware-builder/actions/workflows/build-firmware.yml)
[![Latest Release](https://img.shields.io/github/v/release/coachpo/immortalwrt-firmware-builder?sort=date&style=flat-square&label=Release&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)
[![Downloads (latest)](https://img.shields.io/github/downloads/coachpo/immortalwrt-firmware-builder/latest/total?style=flat-square&label=Downloads&logo=github)](https://github.com/coachpo/immortalwrt-firmware-builder/releases/latest)

[English](README.md) | 简体中文

[构建](#快速开始) · [配置](#配置来源与默认值) · [开发与验证](#开发与验证) · [代理指导](AGENTS.md)

用于构建 **Cudy TR3000 v1（MediaTek Filogic，OpenWrt U-Boot 布局）** ImmortalWrt 固件的种子配置与自动化工作流。所选设备配置为 `cudy_tr3000-v1-ubootmod`，对应[上游设备定义](https://github.com/immortalwrt/immortalwrt/blob/master/target/linux/mediatek/image/filogic.mk)。请使用与硬件版本及引导布局匹配的镜像。

[共用配置脚本](scripts/configure.py) 准备 feeds 与镜像默认值，再通过 `make defconfig` 展开[种子配置](tr3000/seed.config)，也可通过 `make menuconfig` 调整。配置选择了 LuCI、VPN 工具、DoH、QoS 及 USB 网络共享和调制解调器相关软件包。最终软件包和设备默认配置取决于所选 ImmortalWrt 源码与 feeds，可查看生成的 `.config` 和固件 `.manifest` 确认。

## 仓库结构

- `tr3000/seed.config` — 目标与软件包选择的权威配置。
- `tr3000/files/` — 固件覆盖文件，包含最后执行的默认主题设置。
- `scripts/configure.py` — 本地与 CI 共用的 feeds、中立下载源、覆盖文件与配置展开入口。
- `scripts/ci.py` — 缓存 key、完整固件产物收集与构建来源记录。
- `tests/test_configure.py` — 配置与 Shell 控制流的针对性测试。
- `tests/test_ci.py` — 产物、缓存与来源记录的针对性测试；只在本地使用 Git，不创建提交或访问网络。
- `immortalwrt/` — 已忽略的运行时源码检出目录，由本地命令或 CI 填充。
- `Dockerfile` — Ubuntu 22.04 构建环境，使用非 root 的 `builder` 用户运行。
- `.github/workflows/build-firmware.yml` — 手动触发的源码拉取、构建、缓存及 Release 发布工作流。
- `.github/workflows/quick-checks.yml` — 推送、PR 和手动触发的独立快速检查，不构建或发布固件。
- `.github/workflows/cleanup-runs-releases.yml` — 定期清理工作流运行记录与 `immortalwrt-*` Releases。

## 主机构建依赖

使用 x86-64 Linux 主机、大小写敏感文件系统和非 root 构建用户。Ubuntu 22.04 依赖列表统一维护在 [Dockerfile](Dockerfile) 的 `apt-get install` 段；可在匹配的主机安装这些包，或使用下文的容器。CI 单独安装依赖，使用 `ubuntu-latest`，不使用该 Docker 镜像。

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

python3 scripts/configure.py immortalwrt
cd immortalwrt
make menuconfig    # 可选调整
make -j"$(nproc)" V=sc
```

方式 B：使用已有源码树。在本构建器仓库根目录执行 `python3 scripts/configure.py /path/to/immortalwrt`，然后到该源码树编译。脚本保留其他 feeds 和无关覆盖文件，但会用本项目 seed 替换 `.config` 并管理本项目提供的覆盖路径。不要仅复制 seed 跳过脚本，否则缺少主题 feed 和默认设置。

源码与 feeds 必须包含所选设备配置及软件包。种子配置包含 ImmortalWrt 特有的软件包，不能保证在 OpenWrt 源码树中直接使用。

固件镜像与 manifest 生成在 ImmortalWrt 源码树的 `bin/targets/mediatek/filogic/` 目录下。

## GitHub Actions（workflow_dispatch）

打开 **Actions → Build ImmortalWrt firmware → Run workflow** 手动运行。仅推送代码不会触发固件构建。构建任务成功后自动执行 Release 发布任务，没有可选发布开关。

**Quick checks** 在推送、PR 和手动触发时独立运行：执行两个针对性测试文件、默认脚本 Shell 语法、推送/PR 事件范围的空白检查（手动或新分支运行时检查最近提交）与 actionlint 1.7.12（安装了 ShellCheck 时一并调用）。不拉取固件源码或 feeds，不恢复固件缓存，不编译或发布。检查结果不会触发固件工作流，也不作为手动构建的前置依赖。

输入与回退优先级：

- `immortalwrt_ref`：非空工作流输入 → 仓库变量 `IMMORTALWRT_REF` → 上游默认分支。支持分支、标签或 commit SHA。
- `cache_epoch`：非空工作流输入 → 仓库变量 `CACHE_EPOCH` → `v1`。

行为：

- 检出本仓库，然后将 `immortalwrt/immortalwrt` 检出到 `immortalwrt/`，递归检出子模块。
- CI 使用 `ubuntu-latest`，Dockerfile 使用 Ubuntu 22.04，两者是独立的构建环境。
- 执行 `python3 scripts/configure.py immortalwrt --ccache`，复用本地配置流程并启用 `CONFIG_CCACHE=y`。脚本展开配置后检查关键选项。
- 使用所有可用 CPU 线程编译；并行编译失败时，用 `make -j1 V=s` 重试。
- ccache 容量上限为 4 GB。独立的 `ccache` 与 `dl` key 包含 runner 操作系统及架构、`tr3000`、源码 ref、seed hash、cache epoch、运行 ID 与尝试次数。稳定恢复前缀复用最近匹配快照，每次运行尝试自动保存新快照，默认分支变化也无需手动刷新。ccache 仅在编译成功后保存；下载缓存可在配置成功但编译失败时保存。
- `cache_epoch` 仍可手动切换命名空间，不再是刷新快照的必要步骤。回退前缀可能复用旧 epoch，因此改值不保证从空缓存开始。
- 以 `immortalwrt_firmware_tr3000_<YYYYMMDDHHMM>` 为名上传选定的固件文件，保留 7 天；随后发布 `immortalwrt-<ref-or-default>-build<run-number>-<YYYYMMDD-HHMM>` 标签的 Release。不支持的标签字符会替换为下划线。

产物收集步骤预期在 `immortalwrt/bin/targets/mediatek/filogic/` 下找到以下文件：

```text
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-bl31-uboot.fip
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-initramfs-recovery.itb
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-preloader.bin
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod-squashfs-sysupgrade.itb
immortalwrt-mediatek-filogic-cudy_tr3000-v1-ubootmod.manifest
```

五个文件名统一定义在 [scripts/ci.py](scripts/ci.py)。构建和发布两端均先检查所有文件存在且非空，再复制任何文件；收集与来源记录只接受新的目标目录，避免旧附件混入。下载使用明确的 artifact ID，防止固件与来源记录混杂。所选 ref 改变产物命名时更新该列表，不放宽完整性检查。

编译结束后（或配置失败、编译跳过时）单独上传可用的来源记录，保留 7 天：`build-info.json` 记录实际构建器、源码、feeds 提交、源码子模块、配置/编译结果、请求 ref、运行与 runner 信息；`seed.config`、`firmware.config`（存在时）、`feeds.conf` 保留输入；源码有已跟踪改动时才保存 `source.patch`。部分配置不代表展开成功。发布前逐一检查必需来源附件、成功状态与构建器提交，定制源码时还必须有非空补丁。成功发布将来源附件与五个固件产物一起保留，正文显示构建器及源码提交，Release 标签绑定本次工作流提交，避免长时间构建期间分支移动导致标签漂移。可追溯性不等于二进制可复现。

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
cd /workdir
python3 scripts/configure.py immortalwrt
cd immortalwrt
make -j"$(nproc)" V=sc
```

Dockerfile 提供统一的构建环境，但基础镜像、apt 软件包版本没有固定，默认源码及 feeds 也可能变化，因此不保证固件二进制可复现。

## 配置来源与默认值

[seed](tr3000/seed.config) 统一维护显式选择：LuCI、Vantage、简体中文翻译、nftables QoS/防火墙/UPnP、诊断工具、配合 dnsmasq-full 的 DoH、WireGuard/OpenVPN/Tailscale、USB 网络共享与蜂窝调制解调器，以及时区数据（`zoneinfo-core`、`zoneinfo-europe`）。安装欧洲时区数据不代表选定欧洲时区。源码、feeds 依赖和设备默认包经 `make defconfig` 展开；若目标、LuCI、Vantage 或选定的主题翻译丢失，或 `default-settings-chn` 被启用，脚本会报错。

### Vantage 主题

[官方 Vantage feed](https://github.com/anothaDev/luci-theme-vantage) 注册到运行时树的 `feeds.conf`，在 [configure.py](scripts/configure.py) 中固定为 v1.0.20 提交 `0f8d16f2ce25132e6a074575af16468524d2d5dd`。安装沿用 `scripts/feeds`，不下载二进制主题包，不添加设备端软件源。仅选择 `luci-theme-vantage` 和 `luci-i18n-vantage-theme-zh-cn`；独立仪表盘 `luci-app-vantage` 不是主题依赖，不纳入镜像。主题依赖 `luci-base`，使用 ucode 模板，在自身 Makefile 中禁用 CSS 压缩。详见[官方安装文档](https://github.com/anothaDev/luci-theme-vantage/blob/0f8d16f2ce25132e6a074575af16468524d2d5dd/docs/INSTALL.md)。

[最后执行的首次启动脚本](tr3000/files/etc/uci-defaults/zzzz-vantage-theme) 在软件包默认设置后选定 `luci.main.mediaurlbase=/luci-static/vantage`。首次执行也会覆盖 sysupgrade 保留的主题选择；其他保留的设备设置不做迁移。移除 Argon 及其配置界面、翻译的显式选择。Bootstrap 由 `luci` → `luci-light` 实际依赖保留，不是默认主题。

**兼容性边界：** 源码 ref 按工作流输入、仓库变量、上游默认分支依次解析。远端仓库变量目前为 `v24.10.2`，对应源码 `cee53da5b58c6241eced0ef17956adda5515634b` 和固定的 LuCI `dbf5de06f1f3989fab244cc22a43deaa1e3b77b2`；已经验证 Vantage 主题及中文翻译包的元数据可在该树解析。本地示例未指定 ref 时仍跟随 master（`SNAPSHOT`）。之前检查的 master 源码 `a4ba8240d8a1aaef7e8c6f2d65e841a9bfd2b8c5` 与 LuCI `ad75cde88e694b511100576bfbe0a280e5efe6ef` 也具备相应 ucode 主题接入路径。Vantage 官方报告支持 OpenWrt 25.12、24.10（24.10 无线及附加应用覆盖有限），snapshot 未测试；这些源码级检查不等于 ImmortalWrt 上的浏览器或设备运行验证。切换 ref 时重新核实；缺少预期配置结构时明确失败，不走无消费者要求的兼容回退。

### 地区中立默认值

| 来源 | 策略 |
| --- | --- |
| `default-settings-chn` | 显式禁用，展开后检查；阻止上海/CST-8 时区、腾讯/阿里云/国家授时中心/CN NTP 及地区包镜像重写进入固件。 |
| 基础时间与 NTP | 保持已检查的上游 UTC（24.10 的 `UTC`，snapshot 的 `GMT0`）与 `time.apple.com`、`time1.google.com`、`time.cloudflare.com`、`pool.ntp.org`，不选另一个国家。 |
| DNS/DoH | 保持 WAN 下发 DNS 与上游通用 Cloudflare/Google DoH 默认值。供应商目录只是可选项，不是活动预设，予以保留。 |
| 固件软件源 | 保持官方 `downloads.immortalwrt.org`；禁用 `default-settings-chn` 阻止其改写到 `mirrors.vsean.net`。 |
| 构建源码镜像 | 将 Debian/Apache/GNU/kernel/GNOME 镜像列表改为各项目运营的端点，移除腾讯、阿里云、清华、中科大、南大、软件所等默认镜像；GitHub raw 下载直连官方 `raw.githubusercontent.com`，不再经过脚本中硬编码的代理/CDN；LibreSSL 从腾讯优先列表改为 `ftp.openbsd.org`。其他项目列表和包校验值保留。 |
| 语言及无线监管 | 保留中文界面与翻译。不设置无线国家代码，不修改板级或校准数据中的监管信息；设备应按实际部署地点设置合法监管域。 |

这些事实针对已检查的源码、feeds 及全新配置，不涵盖任意 ref、可选包或 sysupgrade 恢复的设置。切换 ref 后重新检查展开配置、所选包默认值与镜像内容。

已检查的 master feeds 还缺少 seed 原有的 `nft-qos`/`luci-app-nft-qos`（含其翻译）及 `luci-i18n-wireguard-zh-cn` 包。本任务保留这些无关选择，不擅自替换 QoS 实现；seed 请求的功能不代表在该 snapshot 中已验证安装。

## 开发与验证

从本构建器仓库根目录执行；针对性测试需要 Python 3、Git 和 Perl，工作流静态检查使用 actionlint（可配合 ShellCheck）：

```bash
python3 -m unittest discover -s tests -p 'test_configure.py' -v
python3 -m unittest discover -s tests -p 'test_ci.py' -v
sh -n tr3000/files/etc/uci-defaults/zzzz-vantage-theme
actionlint
git diff --check
```

测试使用临时树与命令替身，检查准备过程幂等性、feeds/配置顺序、关键选项与 UCI 失败处理，不执行真实 `make defconfig`、UCI 或 LuCI。在具备依赖的 Linux 主机执行 `python3 scripts/configure.py /path/to/immortalwrt`（可加 `--ccache`）验证真实展开：会拉取 feeds 并替换该树 `.config`，不编译固件。检查 `.config`；另行请求构建后再检查 manifest 和全新启动界面。文档/脚本验证默认不执行完整固件构建。

选择修改 seed，准备过程修改共用脚本，镜像默认值修改 `tr3000/files/`。保持两份 README 翻译同步。配置与开发两节承担架构说明和贡献政策，不为凑齐模板建立重复文档。

**兼容性政策：** 不要求向后兼容。授权替换时更新实际调用方、配置、测试和文档，删除范围内被替代的路径。没有明确要求或经核实的消费者时，不添加别名、转换、双路径或旧版回退。

**设计原则：** 未确定的能力、平台档位、配额作为假设，采用较宽松的受支持方案，不因推测收紧限制。假定正常合法使用，不在已接受要求外添加预防性滥用控制或最坏情形处理。说明何种观察结果触发重评，保留既定安全及运行义务。保持职责内聚、易导航，按影响局部修改的实际职责拆分，不以统一行数上限制造碎片或无用抽象。

## 故障排查

- 缺少软件包时，重跑共用配置脚本，检查 feed 错误及生成的 `.config`，确认源码与 feeds 包含 seed 引用的符号。克隆成功不代表包索引或配置展开成功。
- 编译失败时，尝试单线程详细输出：`make -j1 V=s`。
- 重试大型构建前检查磁盘空间；编译输出、中间文件和下载的源码会占用较多空间。
- 收集步骤报告产物缺失或为空时，对照实际文件名检查 `scripts/ci.py` 中的必需列表。
- CI 每次运行尝试自动刷新缓存快照；仅在手动切换命名空间时使用 `cache_epoch`。回退前缀仍可能恢复旧内容。

## 许可证

构建器使用 MIT 许可证，详情见 [LICENSE](LICENSE)。下载的固件组件遵循各自许可证；Vantage 为 GPL-3.0-or-later。
