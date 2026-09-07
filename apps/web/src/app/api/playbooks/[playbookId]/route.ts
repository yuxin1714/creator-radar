import { NextResponse } from "next/server";

async function proxy(request: Request, id: string, method: "GET" | "PATCH") {
  if (method === "PATCH" && request.headers.get("origin") !== new URL(request.url).origin) {
    return NextResponse.json({ message: "请求来源无效。" }, { status: 403 });
  }
  let body: string | undefined;
  if (method === "PATCH") {
    try { body = JSON.stringify(await request.json()); }
    catch { return NextResponse.json({ message: "请求格式无效。" }, { status: 400 }); }
  }
  try {
    const response = await fetch(`${process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1/playbooks/${encodeURIComponent(id)}`, {
      method, body, headers: { "content-type": "application/json" }, cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch { return NextResponse.json({ message: "Skill 服务暂时不可用。" }, { status: 503 }); }
}
export async function GET(request: Request, { params }: { params: Promise<{ playbookId: string }> }) { return proxy(request, (await params).playbookId, "GET"); }
export async function PATCH(request: Request, { params }: { params: Promise<{ playbookId: string }> }) { return proxy(request, (await params).playbookId, "PATCH"); }
