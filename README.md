# 词合 CiHe

把纯词库物料编码为 [rime-wubi](https://github.com/rime-wubi/rime-wubi) 的 Ci 类目词表。词合 CiHe 只读取公开物料契约（UTF-8、一行一个词条、按类目分文件、无编码/频次/来源），不读取词采 CiCai 或[词修 CiXiu](https://github.com/chinese-ci/cixiu) 的内部数据。

- 工程文档：[词铸 CiZhu](https://github.com/chinese-ci/cizhu)（规格、架构、术语、决策）
- 物料契约：[词模 CiMo](https://github.com/chinese-ci/cimo) material 契约（发布形态见 [chinese-dict](https://github.com/chinese-ci/chinese-dict)）
- 类目契约：[词模 CiMo](https://github.com/chinese-ci/cimo) taxonomy 契约
- 目标适配器契约：[词模 CiMo](https://github.com/chinese-ci/cimo) targets/adapter 契约
- 默认目标：[词模 CiMo](https://github.com/chinese-ci/cimo) targets/rime-wubi 契约

词合 CiHe 负责调度、通用校验与构建报告；具体 Ci 产物由 target 适配器生成。v1 只提供 `rime-wubi` 适配器，其它 target 必须显式指定并各自实现契约。

## 职责边界

- **词合 CiHe**：读取物料，经 [imewlconverter](https://github.com/studyzy/imewlconverter) v3.6.0 Docker 生成五笔编码，处置跳过/不可信条目，写出 `wubi86.ci.<slug>.dict.yaml` 与 `build-report.json` / `build-report.md`。类目与顺序从 vendored `taxonomy.json` 读取，不硬编码。
- **[rime-wubi](https://github.com/rime-wubi/rime-wubi) 仓库**：维护基础项目结构，包括三个 schema、prism/OpenCC 配置、字表、主表、README/LICENSE 与发布形态。
- **[rime-wubi/zi](https://github.com/rime-wubi/zi)**：构建 `wubi86.zi.dict.yaml` 字表。

词合 CiHe 不生成、不修改 schema、字表、主表或发布 README。Ci 词表输出到独立目录，由 [rime-wubi](https://github.com/rime-wubi/rime-wubi) 的发布流程组装。

处置规则：生成成功且不含 13 个已知差异字 → 写入词表；跳过或不可信时，含拉丁 → `mixed_latin` 丢弃，字表外 → `out_of_charset` 丢弃，词长 >4 → `too_long_for_runtime` 丢弃，否则交给运行时 encoder（`known_bad_char` / `encoder_error`）。总体跳过率 >0.5% 或单类目 >2% 时构建失败（退出码 2）。

## 运行

```bash
uv sync
uv run python tools/build_converter_image.py
uv run python tools/run_consumer.py \
  --material ../CiCai/tests/golden/material \
  --char-table ../rime-wubi/wubi86.zi.dict.yaml
```

默认产物在 `var/consumer/`：`ci/`（Ci 类目词表）、`build-report.json`、`build-report.md`。`--target` 选择适配器（默认 `rime-wubi`）；`--overall-skip-limit` / `--category-skip-limit` 可调阈值。退出码 0 未超阈值，2 超阈值，1 配置/输入错误。编码只由 [imewlconverter](https://github.com/studyzy/imewlconverter) 生成，不自研编码器。字表只作为输入用于跳过分类，由 `rime-wubi/zi` 构建。

## 组装后验收

`tools/verify_package.py` 在真实 [Rime](https://github.com/rime/rime) 目录部署**组装后的** [rime-wubi](https://github.com/rime-wubi/rime-wubi) 方案包（基础项目 + Ci 词表），创建 librime 会话，按码读取三个 schema 的候选，并断言 `wubi_trad` 的 [OpenCC](https://github.com/BYVoid/OpenCC) 简繁输出：

```bash
uv run python tools/verify_package.py \
  --package ../rime-wubi \
  --report var/package-verify/report.json
```

报告为 JSON，含每个 schema 查到的码与候选、OpenCC 对照词和 `rime_version`。失败退出 1。该工具只做验收，不生成或修改包内文件。

## 许可

[MIT](https://opensource.org/license/mit)，见 `LICENSE` 与 `NOTICE.md`。[imewlconverter](https://github.com/studyzy/imewlconverter) 只作为外部进程调用，不随本仓库分发；镜像只在本地构建，不发布。
