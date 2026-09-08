# 数据库备份与隔离恢复

脚本 `scripts/data_backup.py` 仅依赖 Python 3.11+ 和正在运行的项目 Docker Compose PostgreSQL。Windows 可使用 API 的 `.venv\Scripts\python.exe`；Mac 使用安装好的 `python3`。以下命令从项目根目录执行。

```sh
python3 scripts/data_backup.py backup
python3 scripts/data_backup.py verify data/backups/实际备份目录
python3 scripts/data_backup.py restore data/backups/实际备份目录 --target creator_radar_restore_check
```

每次创建独立备份目录，包含 `database.dump` 与 SHA-256 清单，记录代码提交。使用 PostgreSQL 一致性快照；备份不停止服务，也不覆盖已有文件。`data/` 已被 Git 忽略。

恢复先核对校验和，只允许新建 `creator_radar_restore_` 前缀的隔离数据库，拒绝现有目标和当前工作台库。恢复为单事务；失败时空的隔离库可能保留，不自动删除。脚本不切换应用连接；正式迁移切换需在核对恢复结果、配置凭证并停止旧实例后进行。

## 内容范围

包含数据库中的作品、逐字稿、分析、草稿、生成历史、Skill 内容/版本、标签和监控配置。不包含 `.env`、API Key、媒体缓存、ASR 模型权重或 Redis 队列。数据库本身含用户内容，应通过受控存储传送给目标设备；不能提交到公开仓库。

跨设备恢复需要将整个备份目录复制到目标机器，并在目标机器恢复。GitHub 同步代码不会自动复制这些数据。原来的自动监控设置也在备份中；切换到新实例前停用旧实例的同一监控，避免重复运行。当前仅本机单 API worker 模式。

## 2026-09-08 演练

已创建本机备份 `data/backups/backup-20260908T141551Z-38f4c898`，校验通过，并恢复到独立库 `creator_radar_restore_verify_20260908`。恢复库含 25 条作品、2 个创作项目、4 次生成、2 个 Skill 版本。原工作台连接保持不变；隔离验证库目前保留。

Mac 命令和路径已避免 Windows 特定依赖，但尚未在真实 Mac 设备执行恢复演练。团队上线后还需要服务器自动备份、异地存储、保留周期和恢复权限策略；本工具不是完整灾备系统。
