import { formatDistanceToNow } from 'date-fns';
import { Bot, ChevronDown, ChevronUp, Loader2, Play, AlertTriangle, Info } from 'lucide-react';
import { useState } from 'react';
import { useAgentLog, useRunAgent } from '@/hooks/api/use-agent';
import type { AgentRunLogRead } from '@/lib/api/services/agent.service';

// ---------------------------------------------------------------------------
// Risk level styling
// ---------------------------------------------------------------------------

const RISK_CONFIG: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  low:      { label: 'Low Risk',      bg: 'bg-emerald-500/10', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  moderate: { label: 'Moderate Risk', bg: 'bg-yellow-500/10',  text: 'text-yellow-400',  dot: 'bg-yellow-400' },
  elevated: { label: 'Elevated Risk', bg: 'bg-orange-500/10',  text: 'text-orange-400',  dot: 'bg-orange-400' },
  critical: { label: 'Critical Risk', bg: 'bg-red-500/10',     text: 'text-red-400',     dot: 'bg-red-400' },
};

const ACTION_LABELS: Record<string, string> = {
  compute_score:     'Score computed',
  generate_insight:  'Insight generated',
  queue_push:        'Notification queued',
  flag_risk:         'Risk flagged',
  override_scenario: 'Scenario set',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RiskBadge({ level }: { level: string }) {
  const cfg = RISK_CONFIG[level] ?? RISK_CONFIG.low;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

function ActionPill({ type, result }: { type: string; result: Record<string, unknown> }) {
  const ok = result.status === 'ok' || result.status === 'queued' || result.status === 'flagged';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border ${
      ok
        ? 'bg-muted/40 border-border/40 text-muted-foreground'
        : 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400'
    }`}>
      {ACTION_LABELS[type] ?? type}
    </span>
  );
}

function RunCard({ log, isLatest }: { log: AgentRunLogRead; isLatest: boolean }) {
  const [expanded, setExpanded] = useState(isLatest);
  const risk = RISK_CONFIG[log.risk_level] ?? RISK_CONFIG.low;
  const age = formatDistanceToNow(new Date(log.created_at), { addSuffix: true });

  return (
    <div className={`border rounded-xl overflow-hidden transition-colors ${
      isLatest ? 'border-border/80 bg-card/50' : 'border-border/40 bg-card/20'
    }`}>
      {/* Header row — always visible */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/20 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <RiskBadge level={log.risk_level} />
          <span className="text-xs text-muted-foreground truncate">
            {age} · {log.triggered_by.replace(/_/g, ' ')}
          </span>
        </div>
        {expanded
          ? <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
          : <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />}
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-border/40 space-y-4">
          {/* Observations */}
          {log.observations.length > 0 && (
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-2">
                Observations
              </p>
              <ul className="space-y-1">
                {log.observations.map((obs, i) => (
                  <li key={i} className="flex gap-2 text-sm text-foreground/80">
                    <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${risk.dot}`} />
                    {obs}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Reasoning */}
          {log.reasoning && (
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-2">
                Analysis
              </p>
              <p className="text-sm text-foreground/80 leading-relaxed">{log.reasoning}</p>
            </div>
          )}

          {/* Actions */}
          {log.actions_executed.length > 0 && (
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-2">
                Actions Taken
              </p>
              <div className="flex flex-wrap gap-1.5">
                {log.actions_executed.map((a, i) => (
                  <ActionPill key={i} type={a.type} result={a.result} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

interface AgentReportSectionProps {
  userId: string;
}

export function AgentReportSection({ userId }: AgentReportSectionProps) {
  const { data: logs, isLoading } = useAgentLog(userId);
  const { mutate: runAgent, isPending } = useRunAgent(userId);

  const latest = logs?.[0];

  return (
    <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
      {/* Section header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/40">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">AI Health Report</h3>
          {latest && (
            <span className="text-xs text-muted-foreground">
              · last run {formatDistanceToNow(new Date(latest.created_at), { addSuffix: true })}
            </span>
          )}
        </div>
        <button
          onClick={() => runAgent()}
          disabled={isPending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 disabled:opacity-50 transition-colors"
        >
          {isPending
            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
            : <Play className="h-3.5 w-3.5" />}
          {isPending ? 'Analysing…' : 'Run Analysis'}
        </button>
      </div>

      <div className="p-6">
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading report…
          </div>
        ) : !logs || logs.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
            <Info className="h-4 w-4 shrink-0" />
            No analysis yet. Click <strong className="text-foreground mx-1">Run Analysis</strong> to generate the first report.
          </div>
        ) : (
          <div className="space-y-3">
            {logs.map((log, i) => (
              <RunCard key={log.id} log={log} isLatest={i === 0} />
            ))}
          </div>
        )}

        {latest?.risk_level === 'critical' && (
          <div className="mt-4 flex items-start gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            Critical risk detected. Consider consulting a healthcare professional.
          </div>
        )}
      </div>
    </div>
  );
}
