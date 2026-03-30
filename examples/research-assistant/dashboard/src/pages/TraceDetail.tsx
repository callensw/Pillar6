import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import TraceView from "../components/TraceView";
import { getTrace } from "../api/client";

export default function TraceDetail() {
  const { id } = useParams<{ id: string }>();
  const [trace, setTrace] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (!id) return;
    getTrace(id).then((data) => setTrace(data.trace || {}));
  }, [id]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Trace View</h1>
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
          className="text-blue-400 text-sm font-medium"
        >
          Trace
        </Link>
        <Link
          to={`/research/${id}/costs`}
          className="text-slate-400 hover:text-white text-sm font-medium transition-colors"
        >
          Costs
        </Link>
      </div>

      <TraceView trace={trace} />
    </div>
  );
}
