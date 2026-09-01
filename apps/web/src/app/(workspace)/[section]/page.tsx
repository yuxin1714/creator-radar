import { notFound } from "next/navigation";
import { WorkspacePage } from "@/components/workspace";
import { sections } from "@/lib/navigation";
export function generateStaticParams() { return sections.map(section => ({ section: section.slug })); }
export default async function Page({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!sections.some(item => item.slug === section)) notFound();
  return <WorkspacePage section={section} />;
}
