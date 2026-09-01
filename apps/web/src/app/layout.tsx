import type { Metadata } from "next";
import "./globals.css";
import "./workspace.css";
export const metadata: Metadata = { title: "Creator Radar · 内容情报与创作工作台", description: "跨平台 AI 内容情报与创作工作台" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
