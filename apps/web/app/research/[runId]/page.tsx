"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

interface ResearchSection {
  title: string;
  content: string;
  citations: Citation[];
}

interface Citation {
  id: string;
  url: string;
  title: string;
}

interface ResearchReport {
  runId: string;
  query: string;
  sections?: ResearchSection[];
  status: string;
}


interface ReportState {
  report: ResearchReport | null;
  loading: boolean;
  error: string | null;
}

export default function ResearchReportPage() {
  const params = useParams();
  const runId = params.runId as string;
  const [state, setState] = useState<ReportState>({
    report: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const response = await fetch(
          `/api/research/status/${runId}`
        );
        if (!response.ok) {
          throw new Error("Research run not found");
        }
        const data = await response.json();

        // Map API response to ResearchReport interface
        // Note: sections and citations will be added to the API in a future update
        setState({
          report: {
            runId: data.run_id,
            query: data.query,
            status: data.status,
            sections: data.sections || undefined, // Use API sections if available
          },
          loading: false,
          error: null,
        });
      } catch (err) {
        setState({
          report: null,
          loading: false,
          error: err instanceof Error ? err.message : "Failed to load report",
        });
      }
    };

    fetchReport();
  }, [runId]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (state.loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg">Loading research report...</div>
      </div>
    );
  }

  if (state.error || !state.report) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg text-red-600">{state.error || "Report not found"}</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Research Report</h1>
        <p className="text-gray-600 mb-1">Query: {state.report.query}</p>
        <p className="text-sm text-gray-500">Run ID: {runId}</p>
        <span
          className={`inline-block mt-2 px-3 py-1 rounded-full text-sm ${
            state.report.status === "completed"
              ? "bg-green-100 text-green-800"
              : "bg-yellow-100 text-yellow-800"
          }`}
        >
          {state.report.status}
        </span>
      </div>

      <div className="space-y-8">
        {state.report.sections && state.report.sections.length > 0 ? (
          state.report.sections.map((section, idx) => (
            <section key={idx} className="border-l-4 border-blue-500 pl-6">
              <h2 className="text-2xl font-semibold mb-4">{section.title}</h2>
              <p className="text-gray-700 mb-4 leading-relaxed">
                {section.content}
              </p>

              {section.citations.length > 0 && (
                <div className="mt-4">
                  <h3 className="text-sm font-semibold text-gray-600 mb-2">
                    Citations
                  </h3>
                  <div className="space-y-2">
                    {section.citations.map((citation) => (
                      <div
                        key={citation.id}
                        className="flex items-center justify-between bg-gray-50 p-3 rounded"
                      >
                        <div className="flex-1">
                          <a
                            href={citation.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline"
                          >
                            [{citation.id}] {citation.title}
                          </a>
                        </div>
                        <button
                          onClick={() => copyToClipboard(citation.url)}
                          className="ml-4 px-3 py-1 text-sm bg-gray-200 hover:bg-gray-300 rounded"
                        >
                          Copy
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          ))
        ) : (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
            <p className="text-gray-700">
              Research report sections are not yet available. The research workflow is {state.report.status}.
            </p>
            <p className="text-sm text-gray-500 mt-2">
              Detailed sections and citations will be added when the research completes.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
