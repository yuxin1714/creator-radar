# 初始化验收记录

日期：2026-08-31；基础环境验证完成。

## 已通过
- Node.js 24.20.0、Python 3.13.15、Docker Desktop 可调用。
- Docker Compose 配置检查；PostgreSQL / Redis 容器 healthy。
- Python 虚拟环境依赖安装及 pip check。
- 后端通过 SQLAlchemy 实际连接 PostgreSQL 执行 SELECT 1；Redis PING；Celery 入口导入。
- FastAPI 已在 127.0.0.1:8000 启动，/health 与 /openapi.json 检查通过。
- 后端精确版本清单：apps/api/requirements.lock.txt（Windows / Python 3.13）。

## 前端验证通过
- 用户 npm 11.19.0 安装进程正常退出（exit 0），已生成根 package-lock.json。
- Next.js 16.3.3；TypeScript 5.9.3；typecheck 在构建前后均通过。
- next build 成功，首页 / 和 /_not-found 静态生成完成。
- 正式服务在 127.0.0.1:3000 启动；首页和 CSS 返回 HTTP 200，页面含预期初始化说明。
- 已请求在应用内浏览器打开页面；未执行浏览器自动化或视觉验收。

## 最终状态与限制
- 前端：http://127.0.0.1:3000/；后端：http://127.0.0.1:8000/health 。
- 服务仅监听本机，验证时保持运行；终端/应用退出或电脑睡眠可能中断服务。
- 本次不缺必要开发软件；未验证 app profile 的完整 Docker 镜像构建，也未启动 Celery worker 执行业务任务。
- API /health 只是存活检查；数据库和 Redis 连接由另行的真实连接检查验证。
- 未完成业务端到端功能，因为该阶段仅为项目骨架。
- Python 版本清单用于当前 Windows 环境；Docker 构建当前仍按版本范围安装，并非已锁定的可复现生产构建。

## 存储与权限
- node_modules、.next、Python .venv 均在 F 盘项目中。
- 后续 npm / pip 缓存为 F:/DevTools/Cache/npm 与 F:/DevTools/Cache/pip；本轮已完成的 npm 安装使用了旧的 C 盘缓存路径；后续安装使用 F 盘。
- 已确认 F:/DockerData/disk/docker_data.vhdx 和 F:/DockerData/main/ext4.vhdx 存在。
- 未删除 C 盘旧缓存；未修改系统临时目录。
- 命令在完全访问模式下恢复；不能据此认定受限沙箱问题已修复。

## 范围
没有实现采集、分析、生成等 P0 业务；无真实 API Key；未调用供应商。

## 后续进展
2026-08-31 已完成 P0 导航与链接格式验证切片，当前运行的是新工作台页面。具体范围和复测结果见 P0_LINK_VALIDATION.md。
