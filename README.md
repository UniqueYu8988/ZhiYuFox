# ZhiYuFox / 知语狸

ZhiYuFox 是一个面向 Windows 的 Bilibili AI 视频总结工具。

它会围绕单个视频提取标题、日期与字幕内容，并生成一份更适合阅读、收藏与归档的 Markdown 笔记。当前版本聚焦“视频内容本身”，不做评论分析，不输出 JSON，也不提供视频下载。

## 功能特点

- 输入 BV 号或视频链接，一键生成 AI 视频总结
- 输出统一格式的 Markdown，便于整理和长期保存
- 仅保留更轻量的本地配置：`SESSDATA`、MiniMax API Key、输出目录
- 提供桌面端小窗界面，适合日常快速使用

## 当前输出内容

生成的 Markdown 默认包含：

- 视频标题
- 发布日期
- `视频主题`
- `核心内容`

AI 总结会尽量围绕视频本身展开，并尽量过滤明显的广告、赞助和植入内容。

## 项目结构

```text
assets/                 图标等资源
desktop/                Electron + React 桌面端
docs/                   文档
src/                    Python 抓取与整理逻辑
requirements.txt        Python 依赖
启动 BiliArchive.bat     Windows 启动脚本
```

## 本地运行

### Python 依赖

```bash
pip install -r requirements.txt
```

### 桌面端开发

```bash
cd desktop
npm install
npm run build:web
```

### 生成桌面发布版

```bash
cd desktop
npm run build:mirror
```

发布产物默认位于：

```text
desktop/release/
```

## 本地配置说明

敏感信息只保存在本地文件中，不写入仓库：

- `SESSDATA`
- MiniMax API Key
- 本地窗口状态
- 运行日志

这些内容都已经通过 `.gitignore` 排除。

## 致谢

本项目在功能思路和底层实现上，参考并基于 ProfessorZhi 的项目继续定制开发：

- [ProfessorZhi/BiliArchive](https://github.com/ProfessorZhi/BiliArchive)

感谢朋友 Zhi 提供底层代码基础，让这个项目能够继续发展成现在的形态。

## 关于 Contributors

GitHub 的 `Contributors` 列表不能手动指定，它取决于实际进入仓库历史的 commit 记录。

如果后续希望 ProfessorZhi 出现在该仓库的 `Contributors` 中，比较合适的方式是：

- 邀请他参与协作并提交 commit
- 或在后续合并带有他真实作者信息的提交

在此之前，README 中的“致谢”会是更准确也更体面的表达方式。
