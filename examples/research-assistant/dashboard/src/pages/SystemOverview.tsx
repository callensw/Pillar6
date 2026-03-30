import { useEffect, useState } from "react";
import { getSystemStats, type SystemStats } from "../api/client";

export default function SystemOverview() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getSystemStats()
      .then(setStats)
      .catch((err) => setError(err.message || "Failed to load stats"));
  }, []);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-white">System Overview</h1>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-4 text-sm">
          {error}
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Jobs"
          value={stats?.total_jobs ?? "-"}
        />
        <StatCard
          label="Completed"
          value={stats?.completed_jobs ?? "-"}
          color="text-green-400"
        />
        <StatCard
          label="Failed"
          value={stats?.failed_jobs ?? "-"}
          color="text-red-400"
        />
        <StatCard
          label="Avg Time"
          value={
            stats ? `${stats.avg_completion_time_s.toFixed(1)}s` : "-"
          }
        />
      </div>

      {/* Cost summary */}
      <div className="bg-navy-800 rounded-lg p-6 border border-navy-700">
        <h2 className="text-lg font-semibold text-white mb-4">
          Cost Summary
        </h2>
        <div className="text-3xl font-bold text-white">
          ${stats?.total_cost_usd?.toFixed(4) ?? "0.0000"}
        </div>
        <p className="text-slate-500 text-sm mt-1">
          Total cost across all research jobs
        </p>
      </div>

      {/* Connection status */}
      <div className="bg-navy-800 rounded-lg p-6 border border-navy-700">
        <h2 className="text-lg font-semibold text-white mb-4">
          System Status
        </h2>
        <div className="flex items-center gap-3">
          <span
            className={`w-3 h-3 rounded-full ${
              stats ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <span className="text-slate-300">
            {stats ? "API Connected" : "API Disconnected"}
          </span>
        </div>
        <p className="text-slate-500 text-sm mt-3">
          Start the API server with:{" "}
          <code className="bg-navy-900 px-2 py-1 rounded text-xs">
            python main.py --serve
          </code>
        </p>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color = "text-white",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="bg-navy-800 rounded-lg p-4 border border-navy-700">
      <p className="text-slate-500 text-xs">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}
