# P0 第七轮：创作草稿基础

日期：2026-09-02

## 已完成

- 新增 `CreationProject` 数据模型，区分用户自己的创作与外部参考作品。
- 支持创建、列表、读取和更新草稿项目。
- 创作空间支持填写项目标题和创作想法。
- 独立编辑页支持保存正文草稿、标题和想法。
- 项目按 `local-user` 校验归属，当前仍是单机预览。
- GPT 生成、优化、版本管理和导出暂不伪造结果，等待模型网关配置。

## 页面入口

- `/creation`：创建草稿并查看最近项目。
- `/creation/{project_id}`：编辑标题、想法和正文草稿。

## API

- `GET /api/v1/creation-projects`
- `POST /api/v1/creation-projects`
- `GET /api/v1/creation-projects/{project_id}`
- `PATCH /api/v1/creation-projects/{project_id}`

## 后续依赖

真实分析与生成需要应用级 LLM API 或公司内部兼容网关，包括 Base URL、模型名称、认证方式和调用权限。Codex CLI 的登录能力不能直接作为应用后端凭证。

数据库当前仍由启动时 `create_all` 创建表；正式环境前需要引入迁移工具并完成现有数据升级演练。
