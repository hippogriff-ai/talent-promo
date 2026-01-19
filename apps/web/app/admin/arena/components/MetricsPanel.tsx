"use client";

import { VariantMetrics } from "@/app/hooks/useArena";

interface MetricsPanelProps {
  metrics: Record<string, VariantMetrics>;
}

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  const a = metrics["A"];
  const b = metrics["B"];

  if (!a && !b) return null;

  const formatMs = (ms: number) => (ms / 1000).toFixed(1) + "s";
  const formatTokens = (n: number) => n.toLocaleString();

  const MetricRow = ({ label, valueA, valueB }: { label: string; valueA: string; valueB: string }) => (
    <div className="grid grid-cols-3 gap-2 text-sm py-1">
      <span className="text-gray-600">{label}</span>
      <span className="text-center text-blue-600">{valueA}</span>
      <span className="text-center text-purple-600">{valueB}</span>
    </div>
  );

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h4 className="font-medium mb-3">Performance Metrics</h4>
      <div className="grid grid-cols-3 gap-2 text-sm font-medium border-b pb-2 mb-2">
        <span></span>
        <span className="text-center text-blue-600">Variant A</span>
        <span className="text-center text-purple-600">Variant B</span>
      </div>
      <MetricRow
        label="Duration"
        valueA={a ? formatMs(a.total_duration_ms) : "—"}
        valueB={b ? formatMs(b.total_duration_ms) : "—"}
      />
      <MetricRow
        label="LLM Calls"
        valueA={a ? String(a.total_llm_calls) : "—"}
        valueB={b ? String(b.total_llm_calls) : "—"}
      />
      <MetricRow
        label="Input Tokens"
        valueA={a ? formatTokens(a.total_input_tokens) : "—"}
        valueB={b ? formatTokens(b.total_input_tokens) : "—"}
      />
      <MetricRow
        label="Output Tokens"
        valueA={a ? formatTokens(a.total_output_tokens) : "—"}
        valueB={b ? formatTokens(b.total_output_tokens) : "—"}
      />
      {(a?.ats_score || b?.ats_score) && (
        <MetricRow
          label="ATS Score"
          valueA={a?.ats_score ? `${a.ats_score}%` : "—"}
          valueB={b?.ats_score ? `${b.ats_score}%` : "—"}
        />
      )}
    </div>
  );
}
