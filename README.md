# Creator Radar

本地 AI 内容研究与创作工作台。当前优先个人本机使用；团队账户、服务器购买和云端部署暂缓，方案保留。

## 日常启动

先打开 Docker Desktop，随后双击项目根目录的 **Start-Workbench.cmd**。

工作台入口：http://127.0.0.1:3000/today 。启动器会检查数据库、API 和前端，复用已运行的本项目服务。详细操作与故障排查见 [本地使用说明](docs/LOCAL_USE.md)。

## 当前功能

- 抖音、TikTok、YouTube 作品导入与元数据；本地逐字稿、GPT 内容分析及原文引用核验。
- 抖音创作者每日检查、真实情报流和创作者详情。
- 作品搜索、收藏、标签、归档恢复。
- 按平台、语言、类型、方向和风格创作；手选或自动匹配 Skill。
- 三个创作方向、正文生成、反馈优化、阅读预览、生成历史、保存版本和导出。
- 自定义 Skill、GitHub Skill 注册/同步与匹配条件。
- 统一任务中心、本地任务中断恢复；数据库备份和隔离恢复工具。

调用模型、采集和转写的可用性取决于已配置服务。本机 TikHub 的间歇错误/付费问题尚未解决，用户选择稍后处理；已有数据查看、草稿编辑和保存不受此影响。当前不是已完成的团队在线产品。

## 首次安装

需要 Node.js 22+、Python 3.11+、Docker Compose v2。日常启动器目前适用于 Windows；已安装的机器无需重装。以下从项目根目录执行：

```powershell
npm.cmd ci
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -e ./apps/api
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path apps/api/.env)) { Copy-Item apps/api/.env.example apps/api/.env }
if (!(Test-Path apps/web/.env.local)) { Copy-Item apps/web/.env.example apps/web/.env.local }
```

真实凭证只配置在后端 apps/api/.env；不要放入前端或提交仓库。ASR 需额外安装本地转写依赖并配置模型路径，见 docs/P0_TRANSCRIPT_FOUNDATION.md。本机工具与缓存优先 F 盘；换机器需调整 .npmrc 和模型/缓存路径，不能直接复制 .venv 或 node_modules。

## 数据与验证

PostgreSQL 数据卷保存作品、分析、草稿和 Skill 版本；GitHub 同步代码，不自动同步这些数据。备份与跨设备隔离恢复见 [数据备份说明](docs/DATA_BACKUP_RESTORE.md)。禁止用删除数据卷或恢复 Docker 出厂设置解决一般启动问题。

```powershell
$env:PYTHONPATH='apps/api'
apps/api/.venv/Scripts/python.exe -m unittest discover -s apps/api/tests
npm.cmd run typecheck
npm.cmd run build
```

API 位于 http://127.0.0.1:8000 ，健康检查 /health，接口文档 /docs。当前单 local-user、单 API 进程，不开放公网；Docker app profile 和 Celery 入口尚不是团队版生产部署流程。

[当前进度](docs/CURRENT_PROGRESS.md) · [本地使用](docs/LOCAL_USE.md) · [团队方案（暂缓）](docs/TEAM_DEPLOYMENT_PLAN.md)
