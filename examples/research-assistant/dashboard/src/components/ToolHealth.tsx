interface ToolStatus {
  name: string;
  healthy: boolean;
  circuit_breaker_state: string;
  total_calls: number;
}

interface Props {
  tools: ToolStatus[];
}

export default function ToolHealth({ tools }: Props) {
  if (tools.length === 0) {
    return (
      <div className="text-slate-500 text-sm">No tool data available.</div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {tools.map((tool) => (
        <div
          key={tool.name}
          className="bg-navy-800 rounded-lg p-4 border border-navy-700"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-white text-sm">{tool.name}</span>
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                tool.healthy ? "bg-green-500" : "bg-red-500"
              }`}
            />
          </div>
          <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
            <span>State: {tool.circuit_breaker_state}</span>
            <span>Calls: {tool.total_calls}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
