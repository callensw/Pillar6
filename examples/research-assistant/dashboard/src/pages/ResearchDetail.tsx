import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import AgentTimeline from "../components/AgentTimeline";
import ReportView from "../components/ReportView";
import {
  getResearch,
  connectWebSocket,
  type ResearchJob,
  type AgentEvent,
} from "../api/client";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-500/20 text-slate-400",
  running: "bg-blue-500/20 text-blue-400",
  complete: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
};

export default function ResearchDetail() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<ResearchJob | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;

    // Fetch initial data
    getResearch(id)
      .then((data) => {
        setJob(data);
        setEvents(data.events || []);
      })
      .catch((err) => setError(err.message || "Failed to load research"));

    // Connect WebSocket for real-time updates
    const ws = connectWebSocket(id, (event) => {
      setEvents((prev) => [...prev, event]);
    });

    // Poll for status updates
    const interval = setInterval(() => {
      getResearch(id)
        .then((data) => {
          setJob(data);
          if (data.status === "complete" || data.status === "failed") {
            clearInterval(interval);
          }
        })
        .catch(() => {
          /* polling failure is non-fatal */
        });
    }, 2000);

    return () => {
      ws.close();
      clearInterval(interval);
    };
  }, [id]);

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-4 text-sm">
        {error}
      </div>
    );
  }

  if (!job) {
    return (
      <div className="text-slate-500 text-center py-16">Loading...</div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{job.question}</h1>
          <p className="text-slate-500 text-sm mt-1">
            Job {job.id} &middot;{" "}
            {new Date(job.created_at * 1000).toLocaleString()}
          </p>
        </div>
        <span
          className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
            STATUS_STYLES[job.status] || STATUS_STYLES.pending
          }`}
        >
          {job.status}
        </span>
      </div>

      {/* Navigation tabs */}
      <div className="flex gap-4 border-b border-navy-700 pb-3">
        <Link
          to={`/research/${id}`}
          className="text-blue-400 text-sm font-medium"
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
          className="text-slate-400 hover:text-white text-sm font-medium transition-colors"
        >
          Costs
        </Link>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Agent Timeline */}
        <div className="bg-navy-800 rounded-lg p-6 border border-navy-700">
          <h2 className="text-lg font-semibold text-white mb-4">
            Agent Activity
          </h2>
          <AgentTimeline events={events} />
        </div>

        {/* Report */}
        <div className="bg-navy-800 rounded-lg p-6 border border-navy-700">
          <h2 className="text-lg font-semibold text-white mb-4">
            Research Report
          </h2>
          <ReportView content={job.result} />
        </div>
      </div>
    </div>
  );
}
