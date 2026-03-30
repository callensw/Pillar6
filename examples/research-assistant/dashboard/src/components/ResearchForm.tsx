import { useState } from "react";

interface Props {
  onSubmit: (question: string) => void;
  loading: boolean;
}

export default function ResearchForm({ onSubmit, loading }: Props) {
  const [question, setQuestion] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim() && !loading) {
      onSubmit(question.trim());
      setQuestion("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <input
        type="text"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask a research question..."
        className="flex-1 px-4 py-3 rounded-lg bg-navy-800 border border-navy-700 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !question.trim()}
        className="px-6 py-3 rounded-lg bg-blue-500 text-white font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Researching..." : "Research"}
      </button>
    </form>
  );
}
