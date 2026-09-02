import { NextResponse } from "next/server";

export async function POST(_request: Request, { params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  try {
    const r = await fetch((process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000") + `/api/v1/tasks/${encodeURIComponent(taskId)}/retry`, { method: "POST", signal: AbortSignal.timeout(35000), cache: "no-store" });
    return NextResponse.json(await r.json(), { status: r.status });
  } catch {
    return NextResponse.json({ message: "API 暂时不可用。" }, { status: 503 });
  }
}
