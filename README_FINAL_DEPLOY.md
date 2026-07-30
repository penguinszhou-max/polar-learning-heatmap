# POLAR Learning Charts｜最终统一部署包

## 本包包含

```text
.github/workflows/deploy.yml
scripts/build.py
requirements.txt

public/
├─ index.html
├─ weekly-hours.html
├─ progress.html
├─ polar-progress.html
├─ phase-voyage.html
├─ data.json
├─ weekly-data.json
├─ progress-data.json
├─ polar-progress-data.json
├─ phase-voyage-data.json
└─ assets/
```

## 本次已经解决

- 总航标与章节进度语义分离；
- 当前章节恢复为“当前学习上下文”，不控制总航线；
- 每日不显示目标，只显示实际分钟；
- 总航标恢复四列信息区和实体阶段节点；
- 阶段航线同时显示验收进度与航行进度；
- 小船通过SVG路径API定位，始终贴着航线；
- 章节标题自动去除重复“第1章｜第1章”；
- 阶段划分由章节编号推导，不要求新增Notion字段；
- 一个build.py同时更新全部5个JSON；
- Actions使用唯一artifact名称，避免重新运行产物冲突；
- 素材全部位于仓库本地，不依赖外部图床。

## 上传方式

不要把ZIP文件本身上传到GitHub。

解压后，把下列目录和文件覆盖到仓库根目录：

```text
.github/
scripts/
public/
requirements.txt
```

最方便的方式：

1. 在本地解压；
2. 进入GitHub仓库根目录；
3. 选择 `Add file → Upload files`；
4. 拖入解压后目录中的所有内容；
5. 确认目录层级没有多套一层 `polar-learning-final/`；
6. 提交到 `main`。

提交说明：

```text
Deploy final POLAR learning dashboard
```

## Secrets检查

仓库必须已有：

```text
NOTION_TOKEN
LEARNING_RECORDS_DATA_SOURCE_ID
CHAPTERS_DATA_SOURCE_ID
```

本轮不需要新增Secret。

## 运行

提交后应自动触发。也可以：

```text
Actions
→ Deploy POLAR Learning Charts
→ Run workflow
→ main
```

创建新的运行，不要在旧失败任务中点击 `Re-run jobs`。

成功时构建步骤名称：

```text
Read Notion and build all chart data
```

日志应出现：

```text
统一构建完成：X条正式记录，15章，X个学习日。
已生成：data.json、weekly-data.json、progress-data.json、
polar-progress-data.json、phase-voyage-data.json
```

## 检查网址

```text
https://penguinszhou-max.github.io/polar-learning-heatmap/
https://penguinszhou-max.github.io/polar-learning-heatmap/weekly-hours.html
https://penguinszhou-max.github.io/polar-learning-heatmap/progress.html
https://penguinszhou-max.github.io/polar-learning-heatmap/polar-progress.html
https://penguinszhou-max.github.io/polar-learning-heatmap/phase-voyage.html
```

## 最终页面判定

### 总航标

- 今日只显示实际分钟；
- 本周显示实际 / 计划；
- 总体显示实际 / 326小时；
- 当前章节位于“当前学习上下文”；
- 总航标位置只根据整体累计小时；
- 下方显示当前阶段、下一里程碑、通过章节和计划差额。

### 阶段航线

- 同时显示验收进度与航行进度；
- 船必须位于波浪线路上；
- 第1章内部投入50%时，船约位于阶段航线10%；
- 章节只有在状态变为“已通过”等通过状态后才切换完成岛；
- 当前章高亮；
- 章节悬停显示完整信息；
- 目标岛位于最右侧。

## Notion嵌入高度

部署确认后，建议：

```text
polar-progress.html：540—570px
phase-voyage.html：520—550px
```

Notion右上角保持：

```text
全宽：开启
小字号：关闭
```
