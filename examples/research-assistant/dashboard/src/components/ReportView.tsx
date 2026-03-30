import ReactMarkdown from "react-markdown";

interface Props {
  content: string;
}

export default function ReportView({ content }: Props) {
  if (!content) {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        Report will appear here when research is complete.
      </div>
    );
  }

  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}
