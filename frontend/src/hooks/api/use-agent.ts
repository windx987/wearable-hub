import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentService } from '@/lib/api/services/agent.service';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';

export function useAgentLog(userId: string) {
  return useQuery({
    queryKey: queryKeys.agent.log(userId),
    queryFn: () => agentService.getLog(userId, 5),
    staleTime: 1000 * 60 * 5,
  });
}

export function useRunAgent(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetDate?: string) => agentService.runAgent(userId, targetDate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agent.log(userId) });
      toast.success('Agent analysis complete');
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Agent run failed';
      toast.error(message);
    },
  });
}
