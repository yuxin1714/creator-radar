import { CreationDetail } from "@/components/creation-detail";
export default async function Page({params}:{params:Promise<{projectId:string}>}){return <CreationDetail projectId={(await params).projectId}/>}
