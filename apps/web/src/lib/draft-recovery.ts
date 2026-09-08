import type { DraftSnapshot } from "@/components/draft-history";

export function recoveryKey(projectId: string) {
  return `creator-radar:draft:v1:${projectId}`;
}

export type RecoveredDraft = DraftSnapshot & { base_updated_at?: string };

export function readRecovery(projectId: string): RecoveredDraft | null {
  const raw = sessionStorage.getItem(recoveryKey(projectId));
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    if (typeof data.title !== "string" || typeof data.body !== "string" || typeof data.idea !== "string" || typeof data.output_language !== "string") return null;
    if (!data.brief || !["platform", "content_type", "direction", "style", "playbook_id"].every(key => typeof data.brief[key] === "string")) return null;
    return data;
  } catch { return null; }
}
