import { CreatorDetail } from "@/components/creator-detail";
export default async function Page({params}:{params:Promise<{creatorId:string}>}){
 const {creatorId}=await params;
 return <CreatorDetail creatorId={creatorId}/>;
}
