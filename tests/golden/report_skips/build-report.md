# 构建报告

- target：rime-wubi 1.0.0
- 总体跳过率阈值：>0.50% 失败
- 单类目跳过率阈值：>2.00% 失败
- 结果：超阈值，构建失败
- 超阈值项：总体、下里巴人/日常口语

| 类目 | total | encoded | runtime_only | dropped | skip_rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| 总体 | 7 | 2 | 1 | 4 | 71.4286% |
| 下里巴人/日常口语 | 7 | 2 | 1 | 4 | 71.4286% |

## 下里巴人/日常口语 跳过记录

| 词条 | 处置 | 原因 |
| --- | --- | --- |
| 卵石 | runtime | known_bad_char |
| 卵一二三四 | dropped | too_long_for_runtime |
| 卵龘 | dropped | out_of_charset |
| AA制 | dropped | mixed_latin |
| T恤 | dropped | mixed_latin |
