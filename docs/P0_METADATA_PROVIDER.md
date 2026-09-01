# P0 第三轮：作品元数据 Provider 基础

日期：2026-09-01

## 技术选择

首个适配器使用 TikHub。它为抖音、TikTok 和 YouTube 提供统一 Bearer Token 认证的单条作品接口。Apify 保留为后备方案；其字段、价格和输入取决于具体 Actor，不作为当前业务模型。

## 已完成

- 独立 TikHub 适配器，第三方原始字段不会直接成为页面合同。
- 三平台端点映射及统一的标题、作者、封面、时长、发布时间、指标结果。
- `work_metadata` 独立表，避免修改已有 `works` 表；启动时创建新表。
- 任务状态支持等待 Provider、采集中、元数据完成及失败原因。
- TikHub 未配置时不会联网或计费，任务保持 `WAITING_PROVIDER / PENDING`。
- 鉴权失败、限流、网络错误、空数据和异常响应分别返回可定位错误。
- Celery 注册 `creator_radar.fetch_work_metadata`；本机页面暂用明确的“尝试采集”动作执行同一管线。
- 作品库可显示真实标题和作者；任务中心显示真实阶段与错误。

## 需要用户完成

1. 在 TikHub 官网注册并验证邮箱。
2. 在用户中心创建 API Key，并先查看目标端点价格。密钥只显示一次，应立即保存。
3. 把密钥写入本机 `F:\codex\creator-radar\apps\api\.env` 的 `TIKHUB_API_KEY=` 后面。
4. 不要把密钥发到聊天或写入前端变量。配置后重启 API，再在任务中心尝试采集。

## 真实验收结果

- 用户在本机 `.env` 配置凭证后，执行 2 次受控 TikHub 请求，对应已有的 2 条抖音作品。
- 2 条作品均写入真实标题、作者、封面、时长和互动指标，状态为 `READY`。
- 2 条任务均从 `WAITING_PROVIDER / PENDING` 进入 `METADATA_READY / COMPLETED`。
- 浏览器确认两条真实元数据和完成状态正常渲染，无页面 JavaScript 错误。
- 密钥未读取、打印或写入文档；后续仍需妥善保管并定期轮换。
