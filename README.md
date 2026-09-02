# Creator Radar

跨平台 AI 内容情报与创作工作台。当前已完成七个一级页面、单条作品确认导入、PostgreSQL 持久化、TikHub 元数据任务、真实作品详情，以及抖音/TikTok 本地 GPU 逐字稿闭环。尚未实现分析、生成、账户或监控。
完整范围见 docs/CREATOR_RADAR_V1_SPEC.md。shadcn/ui 已按手动方式预置 components.json、别名、cn 和主题变量；尚未添加业务组件。

## 目录
```text
apps/web/          Next.js + TypeScript + Tailwind + shadcn/ui 基础配置
apps/api/          FastAPI + Celery 入口、模型/服务/Provider/迁移目录预留
packages/          共享契约预留
infrastructure/    基础设施说明
docs/              V1 规格
docker-compose.yml PostgreSQL / Redis 及 app profile
```

## 运行条件
Node.js 22+（自带 npm）、Python 3.11+、Docker Compose v2（运行数据库或全部容器时）。
本机已安装 Node.js 24.20.0、Python 3.13.15 和 Docker Desktop；具体执行验证见 docs/BOOTSTRAP_STATUS.md。
前端已安装成功，使用根 package-lock.json 固定依赖；后端 requirements.lock.txt 记录本次 Windows / Python 3.13 环境的精确依赖版本，不等同于跨平台锁文件。

## 前端（PowerShell，项目根目录）
```powershell
npm.cmd install
Copy-Item apps/web/.env.example apps/web/.env.local
npm.cmd run dev
```
打开 http://127.0.0.1:3000 。首页跳转 /today；顶部“添加”可验证并确认导入链接，作品库和任务中心显示真实数据库记录。其余业务页面为明确标注的空态结构。
检查：npm.cmd run typecheck；npm.cmd run build。
后续需要 UI 组件时，在 apps/web 内按 shadcn 官方方式添加，不提前生成全套组件。

## 后端（PowerShell，项目根目录）
```powershell
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install --cache-dir F:/DevTools/Cache/pip -c apps/api/requirements.lock.txt -e ./apps/api
Copy-Item apps/api/.env.example apps/api/.env
Set-Location apps/api
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
GET http://127.0.0.1:8000/health 为进程存活检查；/docs 为接口文档。
当前 API 会连接 PostgreSQL。`POST /api/v1/links/validate` 安全访问白名单平台页面并展开短链接；`POST /api/v1/imports` 在服务端二次检查后保存作品并创建等待任务；`GET /api/v1/works` 与 `GET /api/v1/tasks` 返回本机数据。当前使用单一 `local-user`，没有登录和多用户隔离。

## 本地基础设施（另开终端，项目根目录）
```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose up -d postgres redis
```
可选启动全部骨架：docker compose --profile app up --build -d。
停止：docker compose --profile app down（保留数据卷）。
配置仅用于本地，端口绑定 127.0.0.1；不直接用于生产。数据库密码如含 URL 特殊字符，须同步处理 DATABASE_URL 的 URL 编码。
Worker 已注册作品元数据任务；页面的手动执行与 Celery 共用同一处理管线。Windows 原生开发可用 solo 池，正式并发开发优先 Docker/Linux：
```powershell
# 在 apps/api 目录，Redis 已启动
.venv/Scripts/python.exe -m celery -A app.worker:celery_app worker --pool=solo --loglevel=info
```

## TikHub 元数据

TikHub 是当前首个作品元数据适配器，支持抖音、TikTok 和 YouTube。API 调用可能计费；未配置密钥时任务保持等待，不会发起请求。将密钥只写入 `apps/api/.env`：
```dotenv
METADATA_PROVIDER=tikhub
TIKHUB_API_KEY=你的密钥
TIKHUB_BASE_URL=https://api.tikhub.io
```
保存后重启 API，再到任务中心点击“尝试采集”。不要把真实密钥发到聊天、写入 `.env.example` 或前端变量。

## 凭证与范围
示例 Key 留空；真实凭证仅放后端 .env，不提交 Git，不放 NEXT_PUBLIC_ 环境变量。
不读取原 aiGongzuotai 项目内容、不改名或搬迁、不初始化远程仓库、不调用供应商。验证阶段已启动本地 PostgreSQL / Redis。
验收状态详见 docs/BOOTSTRAP_STATUS.md。

## 官方框架说明
- https://nextjs.org/docs/app/getting-started/installation
- https://ui.shadcn.com/docs/installation/manual

## 本机存储约定
用户要求：除系统必要文件外，安装文件、项目依赖、构建产物和缓存优先放 F 盘。
- 工具：F:/DevTools；项目：F:/codex/creator-radar。
- 前端 node_modules / .next、后端 .venv 均保存在项目目录。
- 本项目 .npmrc 指定 npm 缓存 F:/DevTools/Cache/npm；换机器时按实际磁盘修改。
- 当前 Python 虚拟环境 pip.ini 指定缓存 F:/DevTools/Cache/pip；重建虚拟环境时使用上面的 --cache-dir 参数。
- 不自动删除或搬迁 C 盘旧缓存；Windows 和工具仍可能使用 C 盘用户配置与临时目录。
- 当前命令执行通过完全访问模式恢复，尚未验证受限沙箱修复。

第一轮验收详见 docs/P0_LINK_VALIDATION.md；持久化导入切片详见 docs/P0_IMPORT_FOUNDATION.md；元数据接入详见 docs/P0_METADATA_PROVIDER.md；详情页详见 docs/P0_WORK_DETAIL.md；逐字稿基础详见 docs/P0_TRANSCRIPT_FOUNDATION.md；创作草稿基础详见 docs/P0_CREATION_FOUNDATION.md。跨设备复制与部署 Skill 想法已记录在 docs/PORTABILITY_BACKLOG.md，待下次专门讨论。
