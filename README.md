# POLAR Learning Dashboard｜最终重构部署包

## 本次修复

- `polar-progress.html` 与 `phase-voyage.html` 均兼容旧版和新版 JSON 字段，部署切换或浏览器缓存时不会再出现 `undefined` 或整页崩溃。
- `build.py` 统一生成五个数据文件，并写入 `schema_version: 3`。
- GitHub Actions 在读取 Notion 前先运行 `scripts/self_test.py`；数据结构不完整时直接阻止部署。
- 总航标保留当前章节作为“学习上下文”，但总航线位置只由累计小时决定。
- 阶段航线同时区分“验收进度”和“航行进度”。
- 小船通过 SVG 路径坐标计算，始终贴合航线。
- 航线改为平缓长波；章节岛放大并上下错落；标签与状态不压在航线上。
- 已通过章节自动使用亮色蓝旗岛；当前章节高亮；未开始章节低饱和。

## 上传

解压后，将下列内容覆盖到仓库根目录：

```text
.github/
scripts/
public/
requirements.txt
```

不要把外层文件夹 `polar-learning-final-rebuild/` 一并套入仓库。

提交信息：

```text
Deploy stable final POLAR dashboard
```

## GitHub Secrets

保持现有三个 Secret：

```text
NOTION_TOKEN
LEARNING_RECORDS_DATA_SOURCE_ID
CHAPTERS_DATA_SOURCE_ID
```

无需新增或修改。

## 正确的 Actions 步骤

```text
Run schema self-test
Read Notion and build all chart data
```

自检成功时出现：

```text
SELF_TEST_OK
```

构建成功时出现：

```text
统一构建完成：X条正式记录，15章，X个学习日。
```

## 页面

```text
https://penguinszhou-max.github.io/polar-learning-heatmap/
https://penguinszhou-max.github.io/polar-learning-heatmap/weekly-hours.html
https://penguinszhou-max.github.io/polar-learning-heatmap/progress.html
https://penguinszhou-max.github.io/polar-learning-heatmap/polar-progress.html
https://penguinszhou-max.github.io/polar-learning-heatmap/phase-voyage.html
```

## Notion 嵌入高度

```text
polar-progress.html：570—600px
phase-voyage.html：555—585px
```
