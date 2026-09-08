# 本地使用

当前优先个人本机使用。团队账户和云端部署方案保留在 TEAM_DEPLOYMENT_PLAN.md，暂不购买服务器、不开放公网。

## 每天启动（当前 Windows 电脑）

1. 打开 Docker Desktop，等待引擎正常。
2. 双击桌面的“Creator Radar 工作台”雷达图标。图形启动器显示简洁的启动进度，后台准备数据库、API 和前端，页面就绪后打开浏览器。
3. 打开 `http://127.0.0.1:3000/today`。重复启动会复用本项目已运行的服务，不杀进程、不重建数据库。

也可在项目根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

桌面入口不显示终端，失败时弹出提示，日志位于 `data/logs/desktop-startup.log`。关闭启动进度窗口只隐藏它，不中断服务启动。原 `Start-Workbench.cmd` 保留为排查入口，会显示命令行窗口。

重新创建桌面入口：运行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-desktop-shortcut.ps1`。此脚本使用 Windows 自带 .NET Framework 编译图形启动器，输出到 Git 忽略的 `data/desktop-launcher/`，不下载额外运行时。图标源文件在 assets/creator-radar.svg，包含七种 ICO 尺寸；修改图标后可运行 `node scripts/build-desktop-icon.cjs` 重新生成。

启动脚本用于已经安装依赖、配置好后端 `.env` 的 Windows 项目。不会覆盖凭证或自动安装软件。脚本仍使用 Next 开发服务，适合当前本地设计与验证阶段。Mac 启动脚本暂未提供，跨设备恢复方法见 DATA_BACKUP_RESTORE.md。

## 可用入口

- 今日情报 `/today`：从近 7 天收录资料中，展示已有分析和引用核验通过的最多 5 条研究精选；不足不凑数。待研究素材单独展示，不等于推荐。
- 对标创作者 `/creators`：主页、每日检查开关与详情。
- 作品库 `/works`：搜索、平台/标签筛选、收藏、归档恢复。
- 作品详情：逐字稿、内容分析、从作品开始创作。
- 创作空间 `/creation`：平台/语言/类型/风格，手选或自动匹配 Skill；方向生成、反馈优化、历史、预览、保存和导出。
- 设置 `/settings`：自定义 Skill、GitHub 注册、同步和匹配条件。
- 设置中的默认语言和平台仅影响以后新建的项目；已有草稿继续保留自己的配置。
- 任务中心 `/tasks`：真实任务状态与错误、对应生成结果。

## 数据与费用

草稿、作品、逐字稿和 Skill 版本保存在 Docker PostgreSQL 数据卷。关闭浏览器不删除数据，也不会停止后台服务。重启电脑后需要再次启动工作台。

浏览已有数据、编辑/保存、历史、收藏标签、导出和条件匹配不调用 GPT/TikHub。主动采集、主页检查和 AI 生成按所配置服务调用。用户暂缓接口付费；TikHub 的间歇 400 与备用接口 402 尚未解决，不影响已有数据编辑。之前开启的每日检查仍保留，可在创作者页面暂停；只有本机服务运行时才能执行。

新遇到欠费或认证失败时，自动检查会进入阻断状态，接口恢复后需手动检查。普通暂时失败仍按原计划等待下一次检查。新添加主页的每日检查默认关闭，需显式勾选开启。

本机 GPU 转写需要已配置的模型路径和依赖；如果取不到媒体，仍可能受 TikHub 可用性影响。每日监控不会自动批量转写或调用 GPT。

## 备份与排查

备份：`apps/api/.venv/Scripts/python.exe scripts/data_backup.py backup`。已完成的备份恢复演练及完整命令见 DATA_BACKUP_RESTORE.md。

- Docker 未就绪：先修复 Docker，再重新双击启动；不要恢复出厂设置或删除数据卷。
- 端口被其他程序占用：脚本会停止并提示，不会替你结束不明进程。
- API 活着但数据库不可用：脚本会检测读取作品接口失败。先确认 PostgreSQL 容器 healthy。
- 页面/API 无法启动：查看 `data/logs/`；脚本新启动的服务会将输出写在那里，已在其他终端启动的服务继续使用原终端日志。
- 不要同时启动第二个 API worker 或额外 Celery worker。当前本地后台任务架构按单 API 进程运行。
- 配置 Key 后需要在没有运行任务时重启 API；本启动器不会中断已运行的任务。

本地界面无团队登录，不用于公网访问。团队上线相关改造不影响本轮本地优先的决定。
# 后台队列补充（2026-09-09）

桌面入口现在一并启动独立后台 worker。任务中心会显示后台就绪与排队数量；未开始的任务在进程重启后继续，执行中意外中断的任务会提示重试。关闭浏览器不取消任务，电脑仍需保持开机。详情见 P0_LOCAL_QUEUE.md。
