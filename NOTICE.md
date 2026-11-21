# 说明

- 本仓库代码采用 [MIT](https://opensource.org/license/mit)；生成的 Ci 词表随 [rime-wubi](https://github.com/rime-wubi/rime-wubi) 方案包以 [LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.html) 发布，纯词库物料采用 [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)。
- [imewlconverter](https://github.com/studyzy/imewlconverter) v3.6.0 只作为外部进程调用，不随本仓库分发。CI 只构建与测试，不发布包含它的镜像；若将来发布包含 imewlconverter 的镜像，按 [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html) 合规。
- 词语编码只由 [imewlconverter](https://github.com/studyzy/imewlconverter) 生成，不自研编码器，不回退外部词库的现成词码。
- 类目名称与代码参照 [GB/T 20093-2022](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=88537A39BE1C3D1B5C6294F70838096E)，地名参照 [GB/T 2260](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=C9C488FD717AFDCD52157F41C3302C6D) / [GB/T 2659](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=FBCE39BE204B54F6F944092C209121F2)；本仓库只引用标准名称与代码，不复刻标准原文或 PDF。
- 字表由 [rime-wubi/zi](https://github.com/rime-wubi/zi) 构建，单字集以《[通用规范汉字表](https://www.gov.cn/zhengce/zhengceku/2013-08/19/content_1289.htm)》8,105 字为基准；标准只引用不复刻。
- 产物按“现状”提供，不附带任何明示或默示担保。
