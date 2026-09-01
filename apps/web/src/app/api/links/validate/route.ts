import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  // Same-origin browser entry; the upstream is fixed, never taken from user input.
  const origin = request.headers.get("origin");
  if (origin && !["http://" + request.headers.get("host"), "https://" + request.headers.get("host")].includes(origin)) {
    return NextResponse.json({ message: "请在工作台内提交链接。" }, { status: 403 });
  }
  try {
    const raw = await request.text();
    if (raw.length > 6000) return NextResponse.json({ message: "分享内容过长，请只粘贴一条链接。" }, { status: 413 });
    const body = JSON.parse(raw);
    if (!body || typeof body !== "object" || typeof body.text !== "string" || !body.text.trim() || body.text.length > 4000) {
      return NextResponse.json({ message: "请输入一条作品链接，最多 4000 字符。" }, { status: 422 });
    }
    const base = process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000";
    const response = await fetch(base + "/api/v1/links/validate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: body.text }), signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    const result = await response.json();
    if (!response.ok && !result.message) return NextResponse.json({ message: "链接未通过验证，请检查输入。" }, { status: 422 });
    return NextResponse.json(result, { status: response.status });
  } catch (error) {
    if (error instanceof SyntaxError) return NextResponse.json({ message: "输入格式不正确。" }, { status: 400 });
    return NextResponse.json({ message: "暂时连接不到验证服务，请确认后端已启动后重试。" }, { status: 503 });
  }
}
