import type { AgentEvent } from "../api/client";

const AGENT_COLORS: Record<string, string> = {
  conductor: "bg-blue-500",
  "researcher-1": "bg-emerald-500",
  "researcher-2": "bg-teal-500",
  analyst: "bg-amber-500",
  system: "bg-slate-500",
};

const EVENT_ICONS: Record<string, string> = {
  start: "\u25B6",
  delegation: "\u2192",
  thinking: "\uD83D\uDCA1",
  tool_call: "\uD83D\uDD27",
  result: "\u2705",
  complete: "\u2714",
  error: "\u2716",
};

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

interface Props {
  events: AgentEvent[];
}

export default function AgentTimeline({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        No agent activity yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {events.map((event, i) => {
        const color = AGENT_COLORS[event.agent] || "bg-slate-600";
        const icon = EVENT_ICONS[event.event_type] || "\u2022";

        return (
          <div key={i} className="flex gap-3 items-start">
            {/* Timeline dot */}
            <div className="flex flex-col items-center pt-1">
              <div className={`w-3 h-3 rounded-full ${color}`} />
              {i < events.length - 1 && (
                <div className="w-px h-full bg-navy-700 mt-1" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 pb-3">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium text-slate-300">
                  {event.agent}
                </span>
                <span className="text-slate-600">{icon}</span>
                <span className="text-slate-500 text-xs">
                  {formatTime(event.timestamp)}
                </span>
              </div>
              <p className="text-slate-400 text-sm mt-1">{event.message}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
