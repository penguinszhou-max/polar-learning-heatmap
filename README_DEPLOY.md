# POLAR 总航标＋阶段航线增量包

## 结果页面

全局总航标：

```text
https://penguinszhou-max.github.io/polar-learning-heatmap/polar-progress.html
```

当前阶段航线：

```text
https://penguinszhou-max.github.io/polar-learning-heatmap/phase-voyage.html
```

## 这次修正了什么

### 极地学习航标

只表达：

- 今日实际学习分钟
- 当前学习周
- 整体课程326小时推进
- 四大阶段总航标

不再显示当前章节和章节2/4小时，因此不会再混淆“章节进度”和“课程总进度”。

### 阶段航线

表达：

- 当前阶段
- 阶段内章节岛
- 当前章节
- 小船位置
- 已完成章节旗帜
- 下一章节
- 阶段目标岛

阶段划分直接由章节编号推导，不要求在Notion新增字段：

```text
1—5：基础语言与海洋结构
6—9：旋转海洋与收支
10—13：极地过程与区域整合
14—15：气候动力与综合验收
```

## 上传前检查

GitHub Repository Secrets中已有：

```text
NOTION_TOKEN
LEARNING_RECORDS_DATA_SOURCE_ID
CHAPTERS_DATA_SOURCE_ID
```

Notion内部连接已能读取：

```text
01｜章节与能力地图
02｜学习记录
```

本轮不需要新增Secret。

## 上传方法

不要上传ZIP文件本身。解压后按目录上传：

```text
.github/workflows/deploy.yml
scripts/build.py
public/polar-progress.html
public/phase-voyage.html
public/polar-progress-data.json
public/phase-voyage-data.json
public/assets/*
```

### 方法一：GitHub网页逐目录上传

1. 进入 `.github/workflows/`
2. 替换 `deploy.yml`
3. 进入 `scripts/`
4. 替换 `build.py`
5. 进入 `public/`
6. 替换 `polar-progress.html`
7. 上传 `phase-voyage.html`
8. 上传两个JSON占位文件
9. 在 `public/` 下新建或进入 `assets/`
10. 上传全部WebP素材

提交到：

```text
main
```

建议提交说明：

```text
Add global beacon and phase voyage
```

## 运行

上传完成后会因push自动运行。

也可手动：

```text
Actions
→ Deploy POLAR Learning Charts
→ Run workflow
→ main
```

不要在旧失败记录中点击Re-run jobs。

## 成功日志

构建步骤应显示：

```text
Read Notion and build voyage data
```

并输出类似：

```text
航标数据构建完成：X条正式记录，15章，X个学习日。
已生成：polar-progress-data.json、phase-voyage-data.json
```

## 检查顺序

先打开：

```text
/phase-voyage.html
```

检查：

- 当前阶段是否为基础阶段
- 第1—5章是否出现
- 船是否位于第1章之前或附近
- 第1章是否高亮
- 已通过章节是否显示完成岛
- 下一站是否正确

再打开：

```text
/polar-progress.html
```

检查：

- 今日只显示实际分钟，不显示每日目标
- 本周为2/20小时
- 总进度为2/326小时
- 不再显示第1章标题

## 注意

此版build.py专门生成两个新组件的数据。仓库现有热力图、周图和累计图的已有JSON文件不会被删除，但若旧版build.py原本同时重建它们，本轮替换后它们不会继续更新。

若确认两个新组件正常，我会在下一版把旧图表的数据生成逻辑重新合并回同一个build.py，形成最终统一构建器。这样做是为了先隔离测试新组件，降低排错复杂度。
