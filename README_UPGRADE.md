# POLAR 学习航标与阶段航线升级包

## 本包内容

```text
.github/workflows/deploy.yml
scripts/build.py
public/polar-progress.html
public/phase-voyage.html
public/polar-progress-data.json
public/phase-voyage-data.json
public/assets/beacon-bg.webp
public/assets/voyage-bg.webp
public/assets/ice-marker.webp
```

## 本次修正

### 极地学习航标
- 只表达全局课程进度
- 删除章节标题、当前单元和章节投入
- 取消每日目标，只显示今日实际正式学习分钟
- 保留本周投入、总课程投入和四阶段总航线

### 阶段航线
- 自动识别当前阶段
- 自动读取阶段内章节
- 已通过章节自动插旗
- 当前章节高亮
- 小船自动移动到当前章节附近
- 自动显示下一章和阶段目标岛

## 上传方法

1. 解压ZIP。
2. 在GitHub仓库中按目录上传并覆盖：
   - `.github/workflows/deploy.yml`
   - `scripts/build.py`
   - `public/polar-progress.html`
   - `public/phase-voyage.html`
   - `public/polar-progress-data.json`
   - `public/phase-voyage-data.json`
   - `public/assets/` 内三个素材
3. 提交到 `main`。
4. 等待新工作流自动运行，或进入：
   `Actions → Deploy POLAR Learning Navigation → Run workflow`
5. 不要在旧失败任务中点击 Re-run jobs。

## 检查地址

```text
https://penguinszhou-max.github.io/polar-learning-heatmap/polar-progress.html
https://penguinszhou-max.github.io/polar-learning-heatmap/phase-voyage.html
```

## 需要保留的Secrets

```text
NOTION_TOKEN
LEARNING_RECORDS_DATA_SOURCE_ID
CHAPTERS_DATA_SOURCE_ID
```

## 数据库要求

`01｜章节与能力地图` 和 `02｜学习记录` 必须共享给同一个Notion内部连接。

## 兼容性

新版 `build.py` 会同时更新：

```text
data.json
weekly-data.json
progress-data.json
polar-progress-data.json
phase-voyage-data.json
```

因此原有热力图、每周学习小时图和累计计划折线图会继续自动更新。
