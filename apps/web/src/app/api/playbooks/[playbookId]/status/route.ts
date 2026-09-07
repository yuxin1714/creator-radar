import { NextResponse } from "next/server";
export async function PATCH(request: Request, { params }: { params: Promise<{ playbookId: string }> }) {
  if (request.headers.get("origin") !== new URL(request.url).origin) return NextResponse.json({ message: "请求来源无效。" }, { status: 403 });
  const { playbookId } = await params;
  let body;
  try { body = await request.json(); } catch { return NextResponse.json({ message: "请求格式无效。" }, { status: 400 }); }
  try {
    const response = await fetch(`${process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1/playbooks/${encodeURIComponent(playbookId)}/status`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(10000) });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch { return NextResponse.json({ message: "状态更新失败，请重试。" }, { status: 503 }); }
}
