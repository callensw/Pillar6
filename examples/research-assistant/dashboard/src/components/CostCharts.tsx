import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { CostData } from "../api/client";

const COLORS = ["#3B82F6", "#22C55E", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"];

interface Props {
  costs: CostData;
}

export default function CostCharts({ costs }: Props) {
  const totalCost = costs.total_cost_usd || 0;
  const totalTokens = costs.total_tokens || 0;

  const byModel = Object.entries(costs.by_model || {}).map(
    ([name, cost], i) => ({
      name,
      value: cost as number,
      fill: COLORS[i % COLORS.length],
    })
  );

  const byAgent = Object.entries(costs.by_agent || {}).map(
    ([name, cost], i) => ({
      name,
      value: cost as number,
      fill: COLORS[(i + 2) % COLORS.length],
    })
  );

  return (
    <div className="space-y-8">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-navy-800 rounded-lg p-6 border border-navy-700 text-center">
          <p className="text-slate-500 text-sm">Total Cost</p>
          <p className="text-3xl font-bold text-white mt-2">
            ${totalCost.toFixed(4)}
          </p>
        </div>
        <div className="bg-navy-800 rounded-lg p-6 border border-navy-700 text-center">
          <p className="text-slate-500 text-sm">Total Tokens</p>
          <p className="text-3xl font-bold text-white mt-2">
            {totalTokens.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6">
        {/* Cost by Model */}
        {byModel.length > 0 && (
          <div className="bg-navy-800 rounded-lg p-6 border border-navy-700">
            <h3 className="text-sm font-medium text-slate-300 mb-4">
              Cost by Model
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={byModel}
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  dataKey="value"
                  label={({ name }) => name}
                >
                  {byModel.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) => `$${v.toFixed(4)}`}
                  contentStyle={{
                    backgroundColor: "#1E293B",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Cost by Agent */}
        {byAgent.length > 0 && (
          <div className="bg-navy-800 rounded-lg p-6 border border-navy-700">
            <h3 className="text-sm font-medium text-slate-300 mb-4">
              Cost by Agent
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={byAgent}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#94A3B8", fontSize: 11 }}
                />
                <YAxis
                  tick={{ fill: "#94A3B8", fontSize: 11 }}
                  tickFormatter={(v: number) => `$${v.toFixed(3)}`}
                />
                <Tooltip
                  formatter={(v: number) => `$${v.toFixed(4)}`}
                  contentStyle={{
                    backgroundColor: "#1E293B",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                  }}
                />
                <Bar dataKey="value">
                  {byAgent.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* No data fallback */}
      {byModel.length === 0 && byAgent.length === 0 && (
        <div className="text-slate-500 text-sm py-8 text-center">
          No cost breakdown data available.
        </div>
      )}
    </div>
  );
}
