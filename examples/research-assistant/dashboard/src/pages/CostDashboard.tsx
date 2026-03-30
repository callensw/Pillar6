import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import CostCharts from "../components/CostCharts";
import { getCosts, type CostData } from "../api/client";

export default function CostDashboard() {
  const { id } = useParams<{ id: string }>();
  const [costs, setCosts] = useState<CostData>({});

  useEffect(() => {
    if (!id) return;
    getCosts(id).then((data) => setCosts(data.costs || {}));
  }, [id]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Cost Dashboard</h1>
        <Link
          to={`/research/${id}`}
          className="text-blue-400 text-sm hover:underline"
        >
          &larr; Back to overview
        </Link>
      </div>

      {/* Navigation tabs */}
      <div className="flex gap-4 border-b border-navy-700 pb-3">
        <Link
          to={`/research/${id}`}
          className="text-slate-400 hover:text-white text-sm font-medium transition-colors"
        >
          Overview
        </Link>
        <Link
          to={`/research/${id}/trace`}
          className="text-slate-400 hover:text-white text-sm font-medium transition-colors"
        >
          Trace
        </Link>
        <Link
          to={`/research/${id}/costs`}
          className="text-blue-400 text-sm font-medium"
        >
          Costs
        </Link>
      </div>

      <CostCharts costs={costs} />
    </div>
  );
}
