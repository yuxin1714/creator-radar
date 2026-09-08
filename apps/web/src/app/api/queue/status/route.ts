import { NextResponse } from "next/server";
export async function GET() {
  try {
    const response = await fetch((process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000") + "/api/v1/queue/status", { cache: "no-store", signal: AbortSignal.timeout(5000) });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ message: "无法读取后台运行状态。" }, { status: 503 });
  }
}
