import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import ResearchForm from "../components/ResearchForm";
import { submitResearch, listJobs, type ResearchJob } from "../api/client";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-500/20 text-slate-400",
  running: "bg-blue-500/20 text-blue-400",
  complete: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
};

export default function Home() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<ResearchJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listJobs()
      .then((data) => setJobs(data.jobs || []))
      .catch((err) => setError(err.message || "Failed to load jobs"));
  }, []);

  const handleSubmit = async (question: string) => {
    setLoading(true);
    setError("");
    try {
      const result = await submitResearch(question);
      navigate(`/research/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit");
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="text-center py-8">
        <h1 className="text-4xl font-bold text-white mb-3">
          Research Assistant
        </h1>
        <p className="text-slate-400 text-lg max-w-2xl mx-auto">
          Ask a research question and a team of AI agents will autonomously
          research, analyse, and produce a structured report.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="max-w-3xl mx-auto bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-4 text-sm">
          {error}
        </div>
      )}

      {/* Search form */}
      <div className="max-w-3xl mx-auto">
        <ResearchForm onSubmit={handleSubmit} loading={loading} />
      </div>

      {/* Recent jobs */}
      {jobs.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">
            Recent Research
          </h2>
          <div className="space-y-2">
            {jobs.map((job) => (
              <Link
                key={job.id}
                to={`/research/${job.id}`}
                className="block bg-navy-800 rounded-lg p-4 border border-navy-700 hover:border-blue-500/50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <p className="text-white font-medium">{job.question}</p>
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium ${
                      STATUS_STYLES[job.status] || STATUS_STYLES.pending
                    }`}
                  >
                    {job.status}
                  </span>
                </div>
                <p className="text-slate-500 text-xs mt-2">
                  {new Date(job.created_at * 1000).toLocaleString()}
                </p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
