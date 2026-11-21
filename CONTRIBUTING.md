# 贡献

## 环境

Python 与 uv 由 mise 管理，版本见 `mise.toml`。同步依赖：

```bash
uv sync
```

部署查码测试需要 [Rime](https://github.com/rime/rime) 的 `rime_deployer` 与共享数据（`default.yaml`、`punctuation.yaml`、`key_bindings.yaml`、`symbols.yaml`、`pinyin_simp.dict.yaml`）。Debian 系安装 `librime-bin` 与 `rime-data-pinyin-simp`，共享数据默认读取 `/usr/share/rime-data`，可用 `CIHE_RIME_SHARED_DATA` 指向其他目录。

## 编码器镜像

编码器使用 [imewlconverter](https://github.com/studyzy/imewlconverter) v3.6.0 Linux x64，运行在 .NET 10 runtime 镜像内。需要单独构建一次：

```bash
uv run python tools/build_converter_image.py
```

## 检查

```bash
uv run pytest
uv run pyright
```

测试使用 `tests/fixtures/material/` 的物料夹具、`tests/golden/rime/` 的黄金 Ci 词表与 `tests/golden/report/` 的黄金构建报告；编码格式与黄金报告测试调用真实 [imewlconverter](https://github.com/studyzy/imewlconverter) Docker，处置/阈值/示例测试使用注入的假编码器，不读取词采 CiCai/[词修 CiXiu](https://github.com/chinese-ci/cixiu) 仓库。部署查码测试面向组装后的 [rime-wubi](https://github.com/rime-wubi/rime-wubi) 包，由外部验收流程覆盖。

## 方案包部署查码

```bash
uv run python tools/verify_package.py \
  --package <方案包> --report var/package-verify/report.json
```

三个 schema 依次加载并查码；`wubi_trad` 额外选一个可简繁转换的词条，比对 `wubi86` 与 `wubi_trad` 的候选。依赖 `librime-bin` 与 Rime 共享数据；`CIHE_RIME_SHARED_DATA` 可覆盖共享数据目录。

## 字表输入

词合 CiHe 不构建字表，只把 `--char-table` 作为跳过分类的输入。字表由 [rime-wubi/zi](https://github.com/rime-wubi/zi) 构建，通常直接使用 [rime-wubi](https://github.com/rime-wubi/rime-wubi) 基础项目中的 `wubi86.zi.dict.yaml`。

## 运行消费者

```bash
uv run python tools/run_consumer.py \
  --material <物料目录> \
  --char-table <rime-wubi>/wubi86.zi.dict.yaml \
  --work-dir var/consumer
```

脚本把物料编码为 Ci 类目词表，写到 `var/consumer/ci/`，并在 `var/consumer/` 写 `build-report.json` 与 `build-report.md`。不生成 schema、字表、主表或发布 README；这些属于 [rime-wubi](https://github.com/rime-wubi/rime-wubi) 基础项目。

退出码：0 未超阈值；2 总体跳过率 >0.5% 或单类目 >2%；1 配置/输入错误。阈值可用 `--overall-skip-limit` / `--category-skip-limit` 调整。
