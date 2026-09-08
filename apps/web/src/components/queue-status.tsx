"use client";
import { useEffect, useState } from "react";

type Queue = { worker_ready: boolean; broker_ready: boolean; pending: number };
export function QueueStatus() {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const response = await fetch("/api/queue/status", { cache: "no-store", signal: controller.signal });
        const data = await response.json();
        if (!response.ok || typeof data.worker_ready !== "boolean" || typeof data.broker_ready !== "boolean" || typeof data.pending !== "number") throw new Error();
        if (!controller.signal.aborted) { setQueue(data); setError(false); }
      } catch { if (!controller.signal.aborted) setError(true); }
      finally { if (!controller.signal.aborted) timer = setTimeout(load, 10000); }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);
  return <p role="status">{error ? "暂时无法确认后台状态，请检查本地服务。" : !queue ? "正在检查后台状态…" : queue.worker_ready && queue.broker_ready ? `后台已就绪 · ${queue.pending} 项排队。关闭页面不影响处理；电脑需保持开机。` : "后台暂不可用，已提交的排队任务保留。请双击桌面工作台图标恢复服务，并确认 Docker 已启动。"}</p>;
}
