import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';

export interface AgentRunLogRead {
  id: string;
  user_id: string;
  triggered_by: string;
  risk_level: 'low' | 'moderate' | 'elevated' | 'critical';
  observations: string[];
  reasoning: string | null;
  actions_planned: Array<{ type: string; params: Record<string, unknown> }>;
  actions_executed: Array<{ type: string; params: Record<string, unknown>; result: Record<string, unknown> }>;
  context_snapshot: Record<string, unknown> | null;
  created_at: string;
}

export const agentService = {
  getLog(userId: string, limit = 5): Promise<AgentRunLogRead[]> {
    return apiClient.get<AgentRunLogRead[]>(API_ENDPOINTS.agentLog(userId), {
      params: { limit },
    });
  },

  runAgent(userId: string, targetDate?: string): Promise<AgentRunLogRead> {
    return apiClient.post<AgentRunLogRead>(API_ENDPOINTS.agentRun(userId), {
      target_date: targetDate ?? null,
      trigger: 'manual',
    });
  },
};
