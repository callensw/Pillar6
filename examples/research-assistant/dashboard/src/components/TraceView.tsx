interface TraceEvent {
  event_id: string;
  event_type: string;
  timestamp_ms: number;
  message: string;
  data: Record<string, unknown>;
  agent_id: string;
}

interface TraceData {
  workflow_id: string;
  trace_id: string;
  total_duration_ms: number;
  completed: boolean;
  events: TraceEvent[];
}

interface Props {
  trace: Record<string, unknown>;
}

export default function TraceView({ trace }: Props) {
  const workflows = Object.entries(trace) as [string, TraceData][];

  if (workflows.length === 0) {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        No trace data available.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {workflows.map(([wfId, data]) => (
        <div key={wfId} className="bg-navy-800 rounded-lg p-4 border border-navy-700">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium text-white">Workflow {wfId}</h3>
              <p className="text-slate-500 text-xs mt-1">
                Trace: {data.trace_id} &middot;{" "}
                {data.total_duration_ms?.toFixed(1)}ms
              </p>
            </div>
            <span
              className={`px-2 py-1 rounded text-xs font-medium ${
                data.completed
                  ? "bg-green-500/20 text-green-400"
                  : "bg-amber-500/20 text-amber-400"
              }`}
            >
              {data.completed ? "Complete" : "Running"}
            </span>
          </div>

          <div className="space-y-2">
            {(data.events || []).map((event: TraceEvent, i: number) => (
              <div
                key={event.event_id || i}
                className="flex items-start gap-3 py-2 border-t border-navy-700 first:border-0"
              >
                <span className="text-xs text-slate-600 font-mono whitespace-nowrap pt-0.5">
                  {event.timestamp_ms
                    ? `+${(event.timestamp_ms % 100000).toFixed(0)}ms`
                    : ""}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-blue-400">
                      {event.event_type}
                    </span>
                    {event.agent_id && (
                      <span className="text-xs text-slate-600">
                        ({event.agent_id})
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-400 mt-0.5">
                    {event.message}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
