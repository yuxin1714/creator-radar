# Creator Radar V1 开发规格
版本：0.7（本地 GPU 逐字稿闭环）｜日期：2026-09-01

> 2026-08-31 本轮授权更新：在阶段 0 基础上实现七个一级页面、统一导航、添加弹窗和单条作品链接格式验证。新增 POST /api/v1/links/validate，由前端同源路由代理。仅做无网络的解析验证，不导入或保存作品，不创建后台任务，不实现账户、采集和 AI。旧文中“本次仅骨架”描述的是初始阶段，以下冻结的 P0/P1/P2 范围不变。完成本轮后等待用户反馈，不继续扩大功能。

> 2026-09-01 授权更新：继续 P0 的单条作品导入基础。白名单平台短链接可安全展开，平台页面响应确认后由用户明确确认导入；后端再次确认并写入 Work，同时创建 `WAITING_PROVIDER / PENDING` 任务。作品库和任务中心只展示真实持久化记录。仍不采集元数据或媒体，不调用 Provider，不做 ASR、分析、生成、账户或监控。

> 2026-09-01 后续授权更新：首个元数据适配器选择 TikHub，三平台数据归一到独立业务模型。未配置密钥时不调用计费接口；配置后任务可获取基础元数据。媒体、字幕、分析、生成、账户和监控仍不在本切片。

> 2026-09-01 详情页更新：作品库可进入单条作品详情，展示真实封面、标题、作者、发布时间、时长、互动指标及数据来源。封面通过按作品 ID 限定的安全代理读取；不提供任意 URL 代理。页面继续明确区分元数据与尚未实现的媒体、字幕、分析和评分。

> 2026-09-01 逐字稿基础更新：新增 Transcript 模型、读取 API 和详情页逐字稿标签。YouTube 可走平台已有字幕检查；抖音与 TikTok 明确进入 ASR 路径。ASR 供应商和预算尚未冻结，因此当前不下载媒体、不安装大模型、不产生转写费用。

> 2026-09-01 本地 ASR 更新：用户授权采用 faster-whisper `large-v3-turbo`，在本机 RTX GPU 上运行。抖音/TikTok 由用户显式启动后获取媒体，临时文件放在 F 盘并在转写结束后删除；逐字稿及时间片段写入 PostgreSQL。ASR 不产生模型 API 费用，媒体信息请求仍可能产生 TikHub 费用。YouTube 平台字幕路径尚未执行。


## 1. 来源与本次交付边界
依据《AI创作工作台》最终产品地图与技术选型，对话 ID：6a94419f-85e0-83e8-a4bc-662690e423ed。
以最终 Review 覆盖早期概念稿：对标博主统一为“对标创作者”；创作空间以 CreationProject 为中心；任务中心是系统处理控制台，不是 Todo。
当前请求仅交付本规格、目录结构、框架配置、占位首页与健康检查。下述 P0 是后续开发范围，不代表本次实现。
本次不创建业务表、不实现业务 API、不执行采集、不调用付费服务、不上线、不迁移或删除原 aiGongzuotai 目录。

## 2. 产品定位与核心路径
跨平台 AI 内容情报与创作工作台：发现值得关注的内容、理解内容为什么有效、转化为自己的中文或英文内容。
主路径：添加 3–5 个创作者 → 抓取作品 → AI 分析 → 今日情报 → AI 拆解 → 开始创作 → 选择方向 → 中文或 English → 生成 → 优化 → 保存到创作空间。
第二路径：粘贴支持平台的视频链接 → 识别 → 分析 → 创作。“任意链接”仅指支持平台和可访问内容，不承诺绕过访问限制。

## 3. 冻结范围
### P0（后续实施）
- 账户 / 基础设置；全局添加入口。
- 抖音、TikTok、YouTube 链接识别；Creator Import、Work Import。
- 抖音创作者监控；TikTok/YouTube 基础监控是否启用取决于 Provider 实测稳定性，不默认承诺。
- 媒体获取、ASR、翻译、内容分析、Content Score。
- 今日情报 Basic、情报流、对标创作者、作品库、作品详情、逐字稿、AI 拆解。
- CreationProject、统一 Creation Workspace、中文生成、英文生成、创作空间。
- 任务中心；错误、空态、加载和处理中状态。
### P1（不作为本次或 P0 依赖）
Radar Score、Radar Momentum、完整 Topic Trend、Creator Timeline、TikTok/YouTube 高级监控、批量添加 Creator、Opportunity 高级聚类、多来源高级创作、中英双版本一键生成、高级语义搜索、Creation History 增强、创作质量评分增强。
### P2
跨平台 CreatorIdentity、趋势预测、Opportunity Index、内容日历、团队协作、自动发布、传播效果追踪、创作到发布表现反馈的学习闭环。
不得因为预留模型或路由就扩大 P0。

## 4. 信息架构
| 路由 | 页面职责 |
| --- | --- |
| /today | 今日情报，精选 Top 3–5，AI 替用户筛选 |
| /feed | 情报流，用户主动发现内容 |
| /creators | 对标创作者 |
| /creators/:id | 创作者详情 |
| /works | 外部作品资产库；紧凑列表优先 |
| /works/:id?tab=analysis | AI 拆解 |
| /works/:id?tab=transcript | 逐字稿 |
| /works/:id?tab=create | 进入统一创作流程 |
| /creation | 用户自己的创作，继续创作优先 |
| /creation/:projectId | 统一 Creation Workspace |
| /tasks | 系统处理进度、失败原因与重试 |
| /settings | 账户与基础偏好 |
这些业务路由本次仅记入规格；代码只提供 / 初始化说明页，避免占位界面被误认为可用产品。

## 5. 技术架构与目录
- apps/web：Next.js App Router、TypeScript、Tailwind CSS、shadcn/ui 手动基础配置。
- apps/api：FastAPI；后续 API 与 Celery worker 共用 Python 包。
- PostgreSQL：业务持久化；Redis：消息 broker / 结果缓存；Celery：耗时流水线。
- Docker Compose：本地 PostgreSQL / Redis，app profile 预留 API / worker / web。
- packages：共享契约预留；以 FastAPI OpenAPI 为未来接口类型来源，不复制维护两套业务模型。
- infrastructure：运行与部署说明；docs：规格。
版本线为实现选择，不属于产品范围；依赖安装后应提交锁文件。当前不声称已安装或构建验证。

## 6. 数据模型草案（不执行迁移）
以下字段与 API 是落地建议，不是原对话中已冻结的具体数据库合同；在对应 P0 切片实现时细化，不能新增产品模块。
所有业务记录使用 UUID、UTC 时间；用户资产带 owner_id，查询和修改均校验归属。
| 对象 | 核心字段与约束 |
| --- | --- |
| Account / Preference | 账户标识；analysis_language、默认 output_language；鉴权方案待实现时定 |
| Creator | owner_id、platform、external_id、display_name、source_url；用户内平台标识去重 |
| Work | owner_id、creator_id（可空）、platform、external_id、source_url、title、source_language、status |
| Transcript | work_id、language、segments、provider；原文与翻译分开保存 |
| Analysis | work_id、analysis_language、schema_version、content_score、结构化结果、证据引用 |
| Insight | 摘要、价值说明、关联 Work、日期；基础精选不依赖高级趋势 |
| Opportunity | 基础创作机会与证据关联；高级聚类延后 |
| CreationProject | owner_id、title、context_type、work_id/opportunity_id/idea、output_language、status、current_version_id |
| Generation | project_id、生成行为类型、模型标识、输入版本、状态；不是项目本身 |
| Version | project_id、version_number、正文、来源 Generation（可空）、创建时间；项目内版本号唯一 |
| Task | owner_id、目标对象、任务类型、当前阶段、状态、进度（可空）、错误摘要、重试次数 |
| MonitoringSubscription | owner_id、creator_id、status、last_checked_at；调度频率待 Provider 验证 |
| WorkMetrics | work_id、captured_at、各平台指标；缺失值为 null，不填 0 |
| Tag / Favorite | 用户范围的作品标签与收藏关系；关系去重 |
CreationContext 三选一：work + workId；opportunity + opportunityId；idea + idea 文本。
Generation 属于 CreationProject；不能把 Work 直接当作用户自己的创作。
媒体文件保存在独立存储位置，数据库存引用；保留与清理策略在媒体阶段确定。

## 7. 状态机与流水线
Work：PENDING → FETCHING → DOWNLOADING → TRANSCRIBING → TRANSLATING → ANALYZING → COMPLETED；任一阶段可进入 FAILED。
不需要翻译或已有可用字幕时允许跳过对应阶段，保留真实阶段记录。
Creation：DRAFT / GENERATING / OPTIMIZING / COMPLETED / ARCHIVED。
Monitoring：ACTIVE / PAUSED / ERROR。
Task 建议：PENDING / RUNNING / COMPLETED / FAILED；保留失败阶段与可读错误，不能用假进度填充。
耗时工作由 Celery 执行；API 返回任务 ID，初期查询状态，不引入额外实时基础设施。
重试必须幂等，保留已完成产物；只有可恢复错误才自动有限重试。认证失效、预算不足等应停止并提示。
定时监控与 Celery beat 在监控切片实现；当前仅预留 worker，无任务与定时器。

## 8. Provider 边界
预留 interfaces：识别链接、获取创作者、列出创作者作品、获取作品元数据、获取媒体；ASR、翻译、内容分析、内容生成各自隔离。
TikHub / Apify 是候选数据服务，不能把其特定字段直接暴露为业务模型；各平台能力通过适配器明确报告。
返回标准结果与错误：unsupported、unavailable、rate_limited、authentication_failed、transient_failure。
外部凭证仅后端读取，禁止 NEXT_PUBLIC_ 前缀。配置超时、限速与有限重试，不绕过平台限制。
URL 导入阶段必须限制协议和平台域名，验证重定向，阻断内网/本机地址以防 SSRF。
外部字幕与作品文本是不可信输入，不能作为系统指令；AI 输出必须校验后保存。
尚未冻结：具体 Provider 套餐、模型、ASR 供应商、预算与监控频率。本次不替用户购买或选择付费套餐。

## 9. API 规划（当前仅实现 GET /health）
前缀建议 /api/v1；统一分页、输入校验、归属校验和安全错误响应。
| 接口组 | 最小职责 |
| --- | --- |
| POST /imports | 链接导入，异步返回 task_id |
| GET /creators、GET /creators/{id} | 创作者与详情 |
| GET /works、GET /works/{id} | 作品检索与详情 |
| GET /works/{id}/transcript、/analysis | 逐字稿与分析结果 |
| GET /today、GET /feed | 基础精选与发现 |
| GET /tasks、GET /tasks/{id}、POST /tasks/{id}/retry | 处理状态与授权重试 |
| POST/GET /creation-projects | 新建及列出项目 |
| GET/PATCH /creation-projects/{id} | 读取与保存草稿 |
| POST /creation-projects/{id}/generations | 异步生成/优化 |
| GET /creation-projects/{id}/versions | 基础版本读取 |
| GET/PATCH /settings | 基础偏好 |
账户认证、收藏、标签、监控订阅的精确接口在相应切片补充。
不为尚未实现的业务提供返回假成功的端点。/health 仅表示 API 进程存活，不代表数据库或供应商可用。

## 10. AI 结构与语言约束
source_language、analysis_language、output_language 独立；P0 输出支持中文与 English，不能默认英文来源只能转中文。
分析结果建议 JSON 字段：schema_version、work_id、analysis_language、summary、hook、structure、key_points、content_score、score_reasons、evidence。
Content Score 为 0–100，维度仅包含选题价值、Hook 强度、信息密度、传播潜力、创作价值；权重和提示词尚未定，禁止伪造精确公式。
evidence 必须关联原作品、原文片段或可用时间戳；缺证据时明确说明。
生成结果建议字段：schema_version、project_id、output_language、direction、title、body、source_references。
实现时用 Pydantic 定义 JSON Schema，验证类型、语言、分数范围和来源关联；不把此示例当作已上线契约。
统一创作流程：选择方向 → 生成内容 → AI 辅助优化 → 保存 / 导出。基础导出格式在创作切片确定。

## 11. UI 原则
AppShell / Sidebar / Topbar 统一；平台、语言、评分、状态、标签、证据等组件复用。
全局“添加”识别作品或创作者；“新建创作”表示创建自己的项目，两个入口不混用。
CTA：开始创作、继续创作、生成内容、重新生成、保存到创作空间、导出。
作品库是外部资产，创作空间优先呈现继续编辑的项目；不加无关统计大屏。
全局搜索与页面筛选语义区分；高级语义搜索仍是 P1。
任务中心展示当前阶段、失败摘要、重试；不引入指派、截止日期和 Todo 管理。
空态、加载、失败、处理中必须完整；Unavailable ≠ Zero。

## 12. 配置与安全
根 .env：Compose 本地参数；apps/api/.env：直接运行后端配置；apps/web/.env.local：前端非敏感配置。
.env.example 只含本地演示值和空 Key；真实凭证不得进 Git、客户端代码或日志。
Compose 端口绑定 127.0.0.1，仅本地开发；示例凭据不可用于生产。
本次不实现账户，API 只开放无业务数据的健康检查；在业务开放前完成鉴权和用户隔离。

## 13. 实施顺序及验收
阶段 0（本次）：规格、工程入口、配置、基础目录；不实现 P0 业务。
阶段 1：账户/配置与持久化基础；单条 Work 导入、任务状态及失败处理。
阶段 2：媒体 → 转写 → 翻译 → 分析 → Content Score → 作品详情。
阶段 3：CreationProject → 中文/英文生成 → 优化 → 保存/基础导出。
阶段 4：Creator 导入与抖音监控 → 今日情报 Basic → 情报流，完成主路径。
每个切片补齐对应 UI 状态与边界验证，禁止提前引入 P1/P2。
P0 验收：两条核心路径用真实可用数据跑通；重复导入不重复创建资产；缺失指标不写 0；失败可定位且安全重试；语言独立；项目可保存并继续；用户资产隔离；凭证不暴露。
阶段 0 验收：前后端入口和配置齐全、无真实 Key、无业务假接口；依赖安装/构建/容器检查须明确标记实际结果。

## 14. 框架参考
- https://nextjs.org/docs/app/getting-started/installation
- https://ui.shadcn.com/docs/installation/manual
本次按官方安装方式准备配置；业务边界来自原对话而不是框架文档。
