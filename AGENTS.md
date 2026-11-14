# 仓库代理指导

## 工作位置与边界

- 本仓库是 Cudy TR3000 v1 U-Boot 布局的构建器，不是 ImmortalWrt 源码仓库。架构、配置策略与贡献规则见 [README_CN.md](README_CN.md#配置来源与默认值)（[English](README.md#configuration-and-defaults)）。
- 目标与包选择在 `tr3000/seed.config`；固件覆盖文件在 `tr3000/files/`；共用配置入口为 `scripts/configure.py`；CI 的缓存、产物与来源记录在 `scripts/ci.py`，对应测试为 `tests/test_configure.py` 和 `tests/test_ci.py`。
- `immortalwrt/` 是忽略的运行时检出目录。不要将生成的 `.config`、feeds、下载或编译输出提交到构建器，也不要仅修改运行时树而漏掉生成它的配置或脚本。
- CI 构建与发布在 `.github/workflows/build-firmware.yml`，清理在 `cleanup-runs-releases.yml`。构建工作流成功后自动发布 Release；本地修改授权不等于触发 CI、发布或清理授权。
- `quick-checks.yml` 独立处理推送、PR 和手动快速检查，不触发或依赖固件构建。保持固件仅手动触发及现有自动发布策略；不能将快速检查接成构建触发器或前置依赖。
- 当前没有需要不同规则的子目录；不要按目录清单机械建立嵌套指导。

## 配置与验证

从构建器根目录执行：

```sh
python3 -m unittest discover -s tests -p 'test_configure.py' -v
python3 -m unittest discover -s tests -p 'test_ci.py' -v
sh -n tr3000/files/etc/uci-defaults/zzzz-vantage-theme
actionlint
git diff --check
```

- 真实配置展开使用 `python3 scripts/configure.py /path/to/immortalwrt`，CI 加 `--ccache`。需要具备 Dockerfile 所列依赖的 Linux 构建环境、大小写敏感文件系统与网络；会拉取 feeds、修改源码镜像配置、复制覆盖文件并替换该树的 `.config`，不编译固件。
- 默认只做与改动相关的检查，不执行完整固件构建或全量回归。命令替身测试不代表真实 `make defconfig`、UCI、主题编译或设备运行成功；交付时区分这些证据。
- 本地、Docker 与 CI 均使用共用配置入口，不能只复制 seed。改动入口时同步调用方及中英文 README。
- CI 产物完整列表只在 `scripts/ci.py` 维护，构建上传与发布前都检查存在且非空；不要用宽泛 glob 代替完整性校验，收集与来源记录使用新目录。来源记录在编译后生成，失败时也保留状态；来源与固件分开上传并按 artifact ID 下载，发布前检查附件齐全、成功状态及构建器提交，并将标签绑定工作流提交。
- 缓存每次运行尝试使用新 key，稳定前缀用于恢复；保留架构隔离及手动 epoch 输入，不退回必须手动刷新才能保存新增内容的固定 key。
- Vantage 使用现有 feeds 机制与脚本中的固定提交。只选主题及其中文翻译，不因主题任务自动添加独立仪表盘。Bootstrap 是 `luci-light` 的实际依赖，不能当作无人使用的旧主题删除。
- 保持 `default-settings-chn` 禁用；配置展开后必须保留目标、LuCI、Vantage 和选定的主题翻译。核对工作流输入和远端仓库变量后才能判断实际 ref，不能仅从本地示例推断 CI 跟随 master。变更 ref 时重查上游默认值及主题契约，不能把 OpenWrt 稳定版的支持声明套用到 ImmortalWrt snapshot。
- 地区中立不等于删除中文或全部中国相关文本。DNS 提供商可选目录不是活动默认值；不得猜测无线国家代码或修改设备监管/校准信息。具体策略以 README 配置节为准。

## 设计与兼容性政策

- 不要求向后兼容。替换时同步实际消费者、配置、测试、文档并移除范围内的旧路径；没有明确要求或已核实消费者时，不添加别名、转换、双路径或旧版回退。
- 对未知能力、配额采用较宽松的受支持方案，记录假设及触发重评的证据，不把推测当限制。正常使用优先；不增加未要求的预防性滥用控制或最坏情形处理，保留既定安全义务。
- 保持职责内聚、便于局部审查；按实际职责拆分，不用统一行数上限或无消费者的抽象制造碎片。详细贡献政策见 [README_CN.md](README_CN.md#开发与验证)。

## 跨上下文工作状态

- 单个上下文可完成的任务不建立状态目录。跨压缩或会话时，只在 `.agent-work/<task-slug>/` 保存一个 `progress.md` 与 `evidence/`；创建时将 `.agent-work/` 加入 `.gitignore`。
- 不在 AGENTS、README、其他正式文档或源码注释中写任务进度。
- 每次完整覆盖 `progress.md`，不追加；字段依次为 `Goal`、`Done`、`Now`、`Next`、`Decisions`。`Done` 每行一项并带证据路径，最后一项引用最近验证；`Next` 仅一个可直接执行的动作，`Decisions` 每行一个决策。
- 每次验证单独存入 `evidence/`，包含准确命令、工作目录、退出码和输出；快照只记录其路径与退出码。
- 恢复时先读快照、检查 `git status` 与 diff，再从记录的目录重跑最近验证；不一致时以仓库为准并修正快照。
- 验证完成后，将需长期保留的结论更新到权威文档并删除本任务目录。其他任务目录只报告，不删除。
