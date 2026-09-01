# P0 第五、六轮：逐字稿基础与本地 GPU 转写

日期：2026-09-01

## 已完成

- 新增原文 Transcript 数据模型：语言、Provider、全文、时间片段、状态和错误分开保存；翻译不混入原文记录。
- 新增 `GET /api/v1/works/{work_id}/transcript`，查询时校验本机 owner。
- YouTube 返回 `PLATFORM_CAPTIONS`，抖音和 TikTok 在未配置 ASR 时返回 `ASR_REQUIRED`。
- 作品详情新增“概览 / 逐字稿”标签，支持 `?tab=transcript` 直接访问。
- 抖音/TikTok 支持用户显式启动本地 GPU 转写；页面每 3 秒轮询状态并显示带时间轴的片段。
- 转写开始时通过 TikHub 获取媒体地址，媒体临时写入 F 盘，成功或失败后均删除。
- 桌面和 390px 手机页面通过浏览器验证，无 JavaScript 错误。

## Provider 事实

- TikHub YouTube 字幕接口只获取视频已有字幕，不进行 AI 语音转写；无字幕结果仍可能计费。
- 抖音和 TikTok 当前需要获取媒体音轨，再交给独立 ASR Provider。

## 本机能力检查

- NVIDIA GeForce RTX 5060 Ti，8 GB 显存；系统内存约 32 GB。
- 没有系统 FFmpeg；faster-whisper 使用 PyAV，可不依赖系统 FFmpeg。
- 已在 API 虚拟环境安装 faster-whisper、CTranslate2、cuBLAS 12 与 cuDNN 9；无需系统级 CUDA Toolkit。
- 模型位于 `F:\DevTools\AI\whisper-models\large-v3-turbo`，约 1.62 GB；下载缓存与临时媒体均位于 F 盘。
- RTX 5060 Ti 使用 `int8_float16` 成功加载模型。

## 真实验收

- 当前抖音作品完成端到端转写：语言 `zh`、562 个时间片段、5,478 个字符。
- API、Next.js 同源代理均返回 `COMPLETED`；媒体缓存完成后为 0 个文件。
- 本地 ASR 不产生模型 API 费用；每次新取媒体地址仍可能计入 TikHub 请求。
