import { NextResponse } from "next/server";

export async function GET(request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  try {
    const response = await fetch(`${process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1/creation-projects/${encodeURIComponent(projectId)}/versions${new URL(request.url).search}`, { cache: "no-store", signal: AbortSignal.timeout(10000) });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ message: "暂时无法读取历史版本。" }, { status: 503 });
  }
}
