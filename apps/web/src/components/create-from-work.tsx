"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle, PenLine } from "lucide-react";
import { Button } from "@/components/ui/button";

export function CreateFromWork({ workId, title }: { workId: string; title: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function create() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/creation-projects", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: `创作：${title}`.slice(0, 200), work_id: workId }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || "无法创建草稿");
      router.push(`/creation/${encodeURIComponent(result.id)}`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "无法创建草稿");
      setBusy(false);
    }
  }
  return <div className="work-creation-action">
    <Button variant="outline" disabled={busy} onClick={create}>
      {busy ? <LoaderCircle className="spin" size={15} /> : <PenLine size={15} />}从这条作品开始创作
    </Button>
    {error && <p role="alert">{error}</p>}
  </div>;
}
