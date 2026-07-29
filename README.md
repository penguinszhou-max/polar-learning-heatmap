# POLAR Learning Heatmap

这是 `POLAR Learning Hub｜极地海洋与气候变化` 的精简自动热力图。

## 它只做什么

1. 读取 Notion 的 `02｜学习记录`
2. 仅统计 `是否计入正式时长 = 勾选` 的记录
3. 按日期汇总 `实际分钟`
4. 生成并发布 GitHub 式热力图

## 它不会做什么

- 不修改 Notion
- 不创建数据库
- 不依赖 06 或 07 数据库
- 不读取课程正文、笔记、未解决问题或下一动作
- 不在公开网页中暴露 Notion Token

## 文件结构

```text
polar-learning-heatmap/
├─ .github/
│  └─ workflows/
│     └─ deploy.yml
├─ scripts/
│  └─ build.py
├─ public/
│  ├─ index.html
│  ├─ data.json
│  └─ .nojekyll
├─ requirements.txt
└─ README.md
```

## 配置前提

### Notion内部连接

在 Notion Developer 后台创建内部连接，并只开启：

- Read content

然后打开 `02｜学习记录`：

```text
右上角 •••
→ 连接
→ 添加连接
→ POLAR Learning Heatmap
```

### GitHub仓库

建议创建公开仓库：

```text
polar-learning-heatmap
```

将本压缩包内容上传到仓库根目录。

## GitHub Secrets

进入：

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

添加：

### NOTION_TOKEN

值为 Notion 内部连接的 Token。不要公开。

### LEARNING_RECORDS_DATA_SOURCE_ID

值为：

```text
1593c426-3b9a-46a5-af73-33bd3162b472
```

## 可选GitHub Variable

进入：

```text
Settings
→ Secrets and variables
→ Actions
→ Variables
```

可添加：

```text
WEEKLY_TARGET_HOURS = 20
```

不添加时默认20小时。

## 开启GitHub Pages

```text
Settings
→ Pages
→ Build and deployment
→ Source
→ GitHub Actions
```

## 首次运行

```text
Actions
→ Deploy POLAR Learning Heatmap
→ Run workflow
```

成功后，Pages地址通常为：

```text
https://你的GitHub用户名.github.io/polar-learning-heatmap/
```

## 嵌入Notion

在主页输入：

```text
/embed
```

粘贴GitHub Pages地址。建议：

- 宽度：所在左栏全宽
- 高度：230—270 px
- 与关键节点形成约 62% : 38% 双栏

## 默认字段名称

脚本默认读取：

```text
日期
实际分钟
是否计入正式时长
```

字段必须保持这些名称和类型：

| 字段 | 类型 |
|---|---|
| 日期 | Date |
| 实际分钟 | Number |
| 是否计入正式时长 | Checkbox |

## 自动更新时间

工作流默认：

- 每15分钟尝试运行一次
- 支持手动运行

GitHub定时任务可能略有延迟，不保证精确到分钟。

## 排错

### 401

检查 `NOTION_TOKEN`。

### 403

检查内部连接是否具有 `Read content` 权限。

### 404

检查：

1. Data Source ID 是否正确
2. `02｜学习记录` 是否已添加该内部连接

### 工作流成功但没有热力方格

检查：

1. `日期`是否有值
2. `实际分钟`是否为数字且大于0
3. `是否计入正式时长`是否勾选

### Notion中无法嵌入

先在浏览器中确认GitHub Pages地址能正常打开，然后使用 `/embed`，不要使用普通书签。
