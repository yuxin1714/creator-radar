import { WorkDetail } from "@/components/work-detail";
export default async function Page({params}:{params:Promise<{workId:string}>}) {
  const {workId}=await params;
  return <WorkDetail workId={workId}/>;
}
