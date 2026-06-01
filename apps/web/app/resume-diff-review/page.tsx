"use client";

import type { MouseEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

type VersionId = string;
type RawDiffKind = "context" | "added" | "removed";
type SideBySideKind = "context" | "changed" | "added" | "removed";
type ReviewStatus = "open" | "applied";
type VersionMenuId = "base" | "compare" | null;

type RawDiffRow = {
  kind: RawDiffKind;
  oldLine?: number;
  newLine?: number;
  text: string;
};

type SideBySideRow = {
  id: string;
  kind: SideBySideKind;
  oldLine?: number;
  oldText?: string;
  newLine?: number;
  newText?: string;
};

type ResumeVersion = {
  id: VersionId;
  label: string;
  summary: string;
  text: string;
};

type ReviewSelection = {
  text: string;
  lineStart: number;
  lineEnd: number;
  top: number;
  left: number;
};

type ReviewThread = {
  id: string;
  versionId: VersionId;
  feedbackRequestId: string;
  lineStart: number;
  lineEnd: number;
  quote: string;
  instruction: string;
  suggestion: string;
  replacement: string;
  status: ReviewStatus;
  previousText?: string;
};

type FeedbackRequest = {
  id: string;
  baseVersionId: VersionId;
  compareVersionId: VersionId;
  targetVersionId: VersionId;
  lineStart: number;
  lineEnd: number;
  selectedText: string;
  instruction: string;
  baseSnapshot: string;
  compareSnapshot: string;
  createdAt: string;
};

type FeedbackRevisionResponse = {
  requestId: string;
  targetVersionId: VersionId;
  lineStart: number;
  lineEnd: number;
  proposedRevision: string;
  rationale: string;
  llmPayload?: unknown;
};

type FeedbackThreadRecord = {
  id: string;
  request: FeedbackRequest;
  revision: FeedbackRevisionResponse;
  status: ReviewStatus;
  previousText?: string | null;
  createdAt: string;
  updatedAt: string;
};

type FeedbackThreadUpdate = {
  status: ReviewStatus;
  previousText?: string | null;
};

const originalResume = `ALEX MORGAN
Product Marketing Manager

SUMMARY
Marketing manager with experience launching software products and working with sales teams.

EXPERIENCE
Product Marketing Manager, Northstar AI
- Worked on product launches for new analytics features.
- Made sales materials and trained account executives.
- Helped with customer interviews and wrote launch notes.

Marketing Associate, BrightLayer
- Supported email campaigns, webinars, and customer stories.
- Reported campaign performance to leadership.

EDUCATION
B.A. Communications, University of Michigan`;

const generatedVersions: ResumeVersion[] = [
  {
    id: "v1",
    label: "Generated v1",
    summary: "Sharper positioning and stronger launch language",
    text: `ALEX MORGAN
Product Marketing Manager

SUMMARY
Product marketing leader for B2B AI products, translating customer insight into launches, sales enablement, and measurable pipeline growth.

EXPERIENCE
Product Marketing Manager, Northstar AI
- Led go-to-market launches for analytics features adopted by enterprise revenue teams.
- Built sales enablement kits, objection handling guides, and product narratives for account executives.
- Turned customer interviews into launch messaging, release notes, and positioning for technical buyers.

Marketing Associate, BrightLayer
- Supported lifecycle campaigns, webinars, and customer stories across SMB and mid-market segments.
- Reported campaign performance to leadership with clear recommendations for next-quarter investment.

EDUCATION
B.A. Communications, University of Michigan`,
  },
  {
    id: "v2",
    label: "Generated v2",
    summary: "More conservative edit that preserves more source phrasing",
    text: `ALEX MORGAN
Product Marketing Manager

SUMMARY
Product marketing manager with experience launching B2B software products, partnering with sales teams, and turning customer insight into clearer positioning.

EXPERIENCE
Product Marketing Manager, Northstar AI
- Managed product launches for new analytics features used by revenue teams.
- Created sales materials and trained account executives on product narrative and buyer objections.
- Synthesized customer interviews into launch notes, release messaging, and technical-buyer positioning.

Marketing Associate, BrightLayer
- Supported email campaigns, webinars, and customer stories for growth programs.
- Reported campaign performance to leadership with recommendations for future investment.

EDUCATION
B.A. Communications, University of Michigan`,
  },
  {
    id: "v3",
    label: "Generated v3",
    summary: "Metric-forward version for leadership and impact scanning",
    text: `ALEX MORGAN
Product Marketing Manager

SUMMARY
Product marketing manager for B2B AI products, connecting customer research, launch strategy, and sales enablement to measurable pipeline outcomes.

EXPERIENCE
Product Marketing Manager, Northstar AI
- Led analytics feature launches for enterprise revenue teams and tracked adoption signals across sales and customer success.
- Created enablement kits, battlecards, and objection handling guidance to improve account executive readiness.
- Converted customer interviews into positioning, release narratives, and launch assets for technical decision makers.

Marketing Associate, BrightLayer
- Supported demand programs including email campaigns, webinars, and customer stories.
- Built campaign reporting summaries with recommendations for pipeline and conversion improvements.

EDUCATION
B.A. Communications, University of Michigan`,
  },
  {
    id: "v4",
    label: "Generated v4",
    summary: "Concise recruiter scan with fewer claims and tighter bullets",
    text: `ALEX MORGAN
Product Marketing Manager

SUMMARY
B2B product marketing manager with experience in launches, sales enablement, customer research, and product messaging.

EXPERIENCE
Product Marketing Manager, Northstar AI
- Led launches for analytics features used by revenue teams.
- Built sales enablement materials and trained account executives on product narrative.
- Used customer interviews to shape messaging, release notes, and positioning.

Marketing Associate, BrightLayer
- Supported email campaigns, webinars, and customer stories.
- Reported campaign performance and recommended next steps to leadership.

EDUCATION
B.A. Communications, University of Michigan`,
  },
  {
    id: "v5",
    label: "Generated v5",
    summary: "Narrative version that emphasizes customer insight and enablement",
    text: `ALEX MORGAN
Product Marketing Manager

SUMMARY
Product marketer who turns customer insight into practical launch plans, sales narratives, and buyer-facing messaging for B2B software teams.

EXPERIENCE
Product Marketing Manager, Northstar AI
- Owned launch messaging for analytics capabilities used by enterprise revenue teams.
- Equipped account executives with sales kits, product narratives, and objection responses.
- Translated customer interviews into launch notes, release messaging, and technical-buyer positioning.

Marketing Associate, BrightLayer
- Coordinated lifecycle campaigns, webinars, and customer stories for growth initiatives.
- Shared campaign performance with leadership and identified investment priorities.

EDUCATION
B.A. Communications, University of Michigan`,
  },
];

const resumeVersions: ResumeVersion[] = [
  {
    id: "original",
    label: "Original",
    summary: "Source resume before generation",
    text: originalResume,
  },
  ...generatedVersions,
];

const initialDraftTexts = resumeVersions.reduce<Record<VersionId, string>>(
  (drafts, version) => ({
    ...drafts,
    [version.id]: version.text,
  }),
  {},
);

const stageSteps = [
  { label: "Start", sub: "drop & go" },
  { label: "Research", sub: "we learn" },
  { label: "Conversation", sub: "you reply" },
  { label: "Draft", sub: "we shape" },
  { label: "Export", sub: "you ship" },
];

const popoverWidth = 360;
const popoverHeight = 260;
const apiBaseUrl = "";

function buildRawLineDiff(original: string, revised: string): RawDiffRow[] {
  const before = original.split("\n");
  const after = revised.split("\n");
  const table = Array.from({ length: before.length + 1 }, () =>
    Array<number>(after.length + 1).fill(0),
  );

  for (let beforeIndex = before.length - 1; beforeIndex >= 0; beforeIndex -= 1) {
    for (let afterIndex = after.length - 1; afterIndex >= 0; afterIndex -= 1) {
      table[beforeIndex][afterIndex] =
        before[beforeIndex] === after[afterIndex]
          ? table[beforeIndex + 1][afterIndex + 1] + 1
          : Math.max(
              table[beforeIndex + 1][afterIndex],
              table[beforeIndex][afterIndex + 1],
            );
    }
  }

  const rows: RawDiffRow[] = [];
  let beforeIndex = 0;
  let afterIndex = 0;
  let oldLine = 1;
  let newLine = 1;

  while (beforeIndex < before.length && afterIndex < after.length) {
    if (before[beforeIndex] === after[afterIndex]) {
      rows.push({
        kind: "context",
        oldLine,
        newLine,
        text: before[beforeIndex],
      });
      beforeIndex += 1;
      afterIndex += 1;
      oldLine += 1;
      newLine += 1;
    } else if (
      table[beforeIndex + 1][afterIndex] >= table[beforeIndex][afterIndex + 1]
    ) {
      rows.push({ kind: "removed", oldLine, text: before[beforeIndex] });
      beforeIndex += 1;
      oldLine += 1;
    } else {
      rows.push({ kind: "added", newLine, text: after[afterIndex] });
      afterIndex += 1;
      newLine += 1;
    }
  }

  while (beforeIndex < before.length) {
    rows.push({ kind: "removed", oldLine, text: before[beforeIndex] });
    beforeIndex += 1;
    oldLine += 1;
  }

  while (afterIndex < after.length) {
    rows.push({ kind: "added", newLine, text: after[afterIndex] });
    afterIndex += 1;
    newLine += 1;
  }

  return rows;
}

function buildSideBySideRows(rawRows: RawDiffRow[]): SideBySideRow[] {
  const rows: SideBySideRow[] = [];
  let index = 0;

  const flushChangeBlock = (removed: RawDiffRow[], added: RawDiffRow[]) => {
    const longest = Math.max(removed.length, added.length);

    for (let blockIndex = 0; blockIndex < longest; blockIndex += 1) {
      const oldRow = removed[blockIndex];
      const newRow = added[blockIndex];

      rows.push({
        id: `row-${rows.length}`,
        kind: oldRow && newRow ? "changed" : oldRow ? "removed" : "added",
        oldLine: oldRow?.oldLine,
        oldText: oldRow?.text,
        newLine: newRow?.newLine,
        newText: newRow?.text,
      });
    }
  };

  while (index < rawRows.length) {
    const row = rawRows[index];

    if (row.kind === "context") {
      rows.push({
        id: `row-${rows.length}`,
        kind: "context",
        oldLine: row.oldLine,
        oldText: row.text,
        newLine: row.newLine,
        newText: row.text,
      });
      index += 1;
      continue;
    }

    const removed: RawDiffRow[] = [];
    const added: RawDiffRow[] = [];

    while (index < rawRows.length && rawRows[index].kind !== "context") {
      if (rawRows[index].kind === "removed") {
        removed.push(rawRows[index]);
      } else {
        added.push(rawRows[index]);
      }

      index += 1;
    }

    flushChangeBlock(removed, added);
  }

  return rows;
}

function buildFullReplacementRows(original: string, revised: string): SideBySideRow[] {
  const before = original.split("\n");
  const after = revised.split("\n");
  const longest = Math.max(before.length, after.length);

  return Array.from({ length: longest }, (_, index) => {
    const oldText = before[index];
    const newText = after[index];

    return {
      id: `replacement-${index}`,
      kind:
        oldText !== undefined && newText !== undefined
          ? oldText === newText
            ? "context"
            : "changed"
          : oldText !== undefined
            ? "removed"
            : "added",
      oldLine: oldText !== undefined ? index + 1 : undefined,
      oldText,
      newLine: newText !== undefined ? index + 1 : undefined,
      newText,
    };
  });
}

function normalizeSnippet(value: string) {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

function isMeaningfulLine(value: string) {
  return normalizeSnippet(value).length > 0;
}

function getDiffStats(original: string, revised: string) {
  const rawRows = buildRawLineDiff(original, revised);
  const additions = rawRows.filter((row) => row.kind === "added").length;
  const removals = rawRows.filter((row) => row.kind === "removed").length;
  const commonMeaningful = rawRows.filter(
    (row) => row.kind === "context" && isMeaningfulLine(row.text),
  ).length;
  const changed = additions + removals;
  const meaningfulTotal =
    original.split("\n").filter(isMeaningfulLine).length +
    revised.split("\n").filter(isMeaningfulLine).length;

  return {
    additions,
    removals,
    changed,
    commonMeaningful,
    fullRewrite: changed / Math.max(1, meaningfulTotal) >= 0.72 && commonMeaningful <= 4,
    rawRows,
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function findReviewLineElement(node: Node | null) {
  if (!node) {
    return null;
  }

  const element =
    node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;

  return element?.closest<HTMLElement>("[data-review-line]") ?? null;
}

async function readFeedbackError(response: Response) {
  try {
    const body = (await response.json()) as { detail?: unknown };

    if (typeof body.detail === "string" && body.detail.length > 0) {
      return body.detail;
    }
  } catch {
    // Fall through to the status-based message.
  }

  return `Feedback revision request failed: ${response.status}`;
}

async function requestFeedbackRevision(
  feedbackRequest: FeedbackRequest,
): Promise<FeedbackRevisionResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/resume/review-feedback/revision`,
    {
      body: JSON.stringify(feedbackRequest),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
  );

  if (!response.ok) {
    throw new Error(await readFeedbackError(response));
  }

  return (await response.json()) as FeedbackRevisionResponse;
}

async function fetchFeedbackThreads(): Promise<FeedbackThreadRecord[]> {
  const response = await fetch(`${apiBaseUrl}/api/resume/review-feedback/threads`);

  if (!response.ok) {
    throw new Error(`Feedback threads request failed: ${response.status}`);
  }

  return (await response.json()) as FeedbackThreadRecord[];
}

async function updateFeedbackThreadStatus(
  requestId: string,
  update: FeedbackThreadUpdate,
) {
  const response = await fetch(
    `${apiBaseUrl}/api/resume/review-feedback/threads/${requestId}`,
    {
      body: JSON.stringify(update),
      headers: { "Content-Type": "application/json" },
      method: "PATCH",
    },
  );

  if (!response.ok) {
    throw new Error(`Feedback thread update failed: ${response.status}`);
  }
}

function threadFromRecord(record: FeedbackThreadRecord): ReviewThread {
  return {
    id: `thread-${record.id}`,
    versionId: record.request.targetVersionId,
    feedbackRequestId: record.id,
    lineStart: record.request.lineStart,
    lineEnd: record.request.lineEnd,
    quote: record.request.selectedText,
    instruction: record.request.instruction,
    replacement: record.revision.proposedRevision,
    suggestion: record.revision.rationale,
    status: record.status,
    previousText: record.previousText ?? undefined,
  };
}

function applyThreadSuggestion(text: string, thread: ReviewThread) {
  const lines = text.split("\n");
  const start = thread.lineStart - 1;
  const end = thread.lineEnd - 1;
  const currentBlock = lines.slice(start, end + 1).join("\n");
  const nextBlock = currentBlock.includes(thread.quote)
    ? currentBlock.replace(thread.quote, thread.replacement)
    : thread.replacement;

  lines.splice(start, end - start + 1, ...nextBlock.split("\n"));

  return lines.join("\n");
}

function lineRangeLabel(start: number, end: number) {
  return start === end ? `Line ${start}` : `Lines ${start}-${end}`;
}

function OrchardMark({ size = 28 }: { size?: number }) {
  return (
    <div
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center rounded-full"
      style={{
        width: size,
        height: size,
        background:
          "radial-gradient(circle at 30% 28%, #fff4c2 0%, var(--y-500) 60%, var(--y-600) 100%)",
      }}
    >
      <span
        className="font-serif italic leading-none text-[var(--ink)]"
        style={{
          fontFamily: "Instrument Serif, Georgia, serif",
          fontSize: size * 0.58,
          marginTop: size * -0.06,
        }}
      >
        tp
      </span>
    </div>
  );
}

function StageStrip() {
  const currentStage = 3;

  return (
    <section className="border-b border-[var(--line)] bg-[linear-gradient(180deg,rgba(255,248,220,0.55),rgba(251,247,236,0))]">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-center overflow-x-auto px-5 py-4">
        {stageSteps.map((stage, index) => {
          const isDone = index < currentStage;
          const isActive = index === currentStage;

          return (
            <div
              className="flex min-w-max items-center"
              key={stage.label}
            >
              <div className="flex min-w-24 flex-col items-center gap-2 px-3">
                <div
                  className={[
                    "flex h-8 w-8 items-center justify-center rounded-full border text-sm font-semibold",
                    isActive
                      ? "border-transparent bg-[var(--y-500)] text-[var(--ink)] shadow-[0_0_0_6px_rgba(230,172,0,0.16)]"
                      : isDone
                        ? "border-transparent bg-[var(--ink)] text-[var(--y-300)]"
                        : "border-dashed border-[var(--line)] bg-[var(--surface)] text-[var(--muted)]",
                  ].join(" ")}
                >
                  {isDone ? (
                    <svg
                      aria-hidden="true"
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 16 16"
                    >
                      <path
                        d="M3 8.5 6.5 12 13 4.5"
                        stroke="currentColor"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                      />
                    </svg>
                  ) : (
                    index + 1
                  )}
                </div>
                <div className="text-center">
                  <div
                    className={[
                      "text-sm font-medium",
                      isActive || isDone
                        ? "text-[var(--ink)]"
                        : "text-[var(--muted)]",
                    ].join(" ")}
                  >
                    {stage.label}
                  </div>
                  <div
                    className={[
                      "mt-0.5 text-xs italic",
                      isActive ? "text-[var(--y-700)]" : "text-[var(--muted)]",
                    ].join(" ")}
                    style={{ fontFamily: "Instrument Serif, Georgia, serif" }}
                  >
                    {stage.sub}
                  </div>
                </div>
              </div>
              {index < stageSteps.length - 1 ? (
                <svg
                  aria-hidden="true"
                  className="-mt-7 h-5 w-14 shrink-0"
                  fill="none"
                  preserveAspectRatio="none"
                  viewBox="0 0 60 18"
                >
                  <path
                    d="M0 9 Q15 0 30 9 T60 9"
                    stroke={isDone ? "var(--y-500)" : "var(--line)"}
                    strokeDasharray={isDone ? "0" : "3 4"}
                    strokeLinecap="round"
                    strokeWidth="1.5"
                  />
                </svg>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SummaryPill({
  kind,
  count,
}: {
  kind: "added" | "removed";
  count: number;
}) {
  const added = kind === "added";

  return (
    <div
      className={[
        "flex min-w-24 flex-col items-start gap-1 rounded-lg border px-4 py-3",
        added
          ? "border-[rgba(47,138,79,0.30)] bg-[rgba(47,138,79,0.08)] text-[#1f6b3a]"
          : "border-[rgba(178,58,42,0.25)] bg-[rgba(178,58,42,0.07)] text-[#9c3a28]",
      ].join(" ")}
    >
      <span className="text-xs font-medium">{added ? "Added" : "Removed"}</span>
      <strong className="font-mono text-lg leading-none">
        {added ? "+" : "-"}
        {count}
      </strong>
    </div>
  );
}

function VersionPicker({
  label,
  value,
  options,
  open,
  align = "left",
  onChange,
  onOpenChange,
}: {
  label: string;
  value: VersionId;
  options: Array<ResumeVersion & { edited: boolean }>;
  open: boolean;
  align?: "left" | "right";
  onChange: (value: VersionId) => void;
  onOpenChange: (open: boolean) => void;
}) {
  const current = options.find((option) => option.id === value);

  return (
    <div className="relative">
      <button
        aria-expanded={open}
        className="inline-flex min-h-10 min-w-48 items-center justify-between gap-3 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 text-left text-sm font-semibold text-[var(--ink)] shadow-[var(--sh-1)] transition hover:border-[var(--ink-3)] focus:border-[var(--y-500)] focus:outline-none focus:ring-4 focus:ring-[rgba(239,188,34,0.18)]"
        onClick={() => onOpenChange(!open)}
        type="button"
      >
        <span className="min-w-0">
          <span className="sr-only">{label}: </span>
          {current?.label}
          {current?.edited ? " (edited)" : ""}
        </span>
        <svg
          aria-hidden="true"
          className="h-4 w-4 shrink-0 text-[var(--muted)]"
          fill="none"
          viewBox="0 0 16 16"
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.6"
          />
        </svg>
      </button>

      {open ? (
        <>
          <button
            aria-label="Close version menu"
            className="fixed inset-0 z-10 cursor-default"
            onClick={() => onOpenChange(false)}
            tabIndex={-1}
            type="button"
          />
          <div
            className={[
              "absolute top-11 z-20 w-80 rounded-lg border border-[var(--line)] bg-[var(--surface)] p-1.5 shadow-[0_20px_50px_-16px_rgba(80,60,0,0.18)]",
              align === "right" ? "right-0" : "left-0",
            ].join(" ")}
            role="menu"
          >
            {options.map((option) => (
              <button
                className={[
                  "block w-full rounded-md px-3 py-2 text-left transition hover:bg-[var(--surface-tint)]",
                  option.id === value ? "bg-[var(--y-50)]" : "bg-transparent",
                ].join(" ")}
                key={option.id}
                onClick={() => {
                  onChange(option.id);
                  onOpenChange(false);
                }}
                role="menuitem"
                type="button"
              >
                <span className="block text-sm font-semibold text-[var(--ink)]">
                  {option.label}
                  {option.edited ? " (edited)" : ""}
                </span>
                <span className="mt-0.5 block text-xs leading-5 text-[var(--ink-3)]">
                  {option.summary}
                </span>
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function Home() {
  const [baseVersionId, setBaseVersionId] = useState<VersionId>("original");
  const [compareVersionId, setCompareVersionId] = useState<VersionId>("v1");
  const [versionDrafts, setVersionDrafts] =
    useState<Record<VersionId, string>>(initialDraftTexts);
  const [reviewSelection, setReviewSelection] = useState<ReviewSelection | null>(
    null,
  );
  const [feedbackDraft, setFeedbackDraft] = useState("");
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [reviewThreads, setReviewThreads] = useState<ReviewThread[]>([]);
  const [feedbackRequests, setFeedbackRequests] = useState<FeedbackRequest[]>([]);
  const [versionMenu, setVersionMenu] = useState<VersionMenuId>(null);
  const diffRef = useRef<HTMLDivElement | null>(null);

  const baseVersion = resumeVersions.find(
    (version) => version.id === baseVersionId,
  );
  const compareVersion = resumeVersions.find(
    (version) => version.id === compareVersionId,
  );
  const baseText = versionDrafts[baseVersionId];
  const compareText = versionDrafts[compareVersionId];
  const stats = useMemo(
    () => getDiffStats(baseText, compareText),
    [baseText, compareText],
  );
  const sideBySideRows = useMemo(
    () =>
      stats.fullRewrite
        ? buildFullReplacementRows(baseText, compareText)
        : buildSideBySideRows(stats.rawRows),
    [baseText, compareText, stats.fullRewrite, stats.rawRows],
  );
  const versionOptions = useMemo(
    () =>
      resumeVersions.map((version) => ({
        ...version,
        edited: versionDrafts[version.id] !== version.text,
      })),
    [versionDrafts],
  );
  const activeThreads = reviewThreads.filter(
    (thread) => thread.versionId === compareVersionId,
  );
  const activeRequestCount = feedbackRequests.filter(
    (request) => request.compareVersionId === compareVersionId,
  ).length;
  const pendingFeedbackCount = activeThreads.filter(
    (thread) => thread.status === "open",
  ).length;
  const appliedFeedbackCount = activeThreads.filter(
    (thread) => thread.status === "applied",
  ).length;
  const canSubmitFeedback =
    Boolean(reviewSelection) &&
    feedbackDraft.trim().length > 0 &&
    !isSubmittingFeedback;

  useEffect(() => {
    let mounted = true;

    fetchFeedbackThreads()
      .then((records) => {
        if (!mounted) {
          return;
        }

        setFeedbackRequests(records.map((record) => record.request));
        setReviewThreads(records.map(threadFromRecord));
      })
      .catch(() => {
        // The UI still works locally if the API is not running.
      });

    return () => {
      mounted = false;
    };
  }, []);

  const clearSelection = () => {
    window.getSelection()?.removeAllRanges();
    setReviewSelection(null);
    setFeedbackDraft("");
    setFeedbackError(null);
  };

  const openLineFeedback = (
    lineNumber: number,
    lineText: string,
    event: MouseEvent<HTMLButtonElement>,
  ) => {
    const rect = event.currentTarget.getBoundingClientRect();

    window.getSelection()?.removeAllRanges();
    setFeedbackDraft("");
    setFeedbackError(null);
    setReviewSelection({
      text: lineText || "Blank line",
      lineStart: lineNumber,
      lineEnd: lineNumber,
      left: clamp(rect.left, 16, window.innerWidth - popoverWidth - 16),
      top: clamp(rect.bottom + 8, 16, window.innerHeight - popoverHeight - 16),
    });
  };

  const captureGeneratedSelection = () => {
    const selection = window.getSelection();

    if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
      setReviewSelection(null);
      return;
    }

    const anchorElement = findReviewLineElement(selection.anchorNode);
    const focusElement = findReviewLineElement(selection.focusNode);

    if (
      !anchorElement ||
      !focusElement ||
      anchorElement.dataset.reviewVersion !== compareVersionId ||
      focusElement.dataset.reviewVersion !== compareVersionId
    ) {
      setReviewSelection(null);
      return;
    }

    const selected = selection.toString().trim();

    if (!selected) {
      setReviewSelection(null);
      return;
    }

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const anchorLine = Number(anchorElement.dataset.reviewLine);
    const focusLine = Number(focusElement.dataset.reviewLine);

    setReviewSelection({
      text: selected,
      lineStart: Math.min(anchorLine, focusLine),
      lineEnd: Math.max(anchorLine, focusLine),
      left: clamp(rect.left, 16, window.innerWidth - popoverWidth - 16),
      top: clamp(rect.bottom + 8, 16, window.innerHeight - popoverHeight - 16),
    });
    setFeedbackError(null);
  };

  const submitFeedback = async () => {
    if (!reviewSelection || !feedbackDraft.trim()) {
      return;
    }

    const instruction = feedbackDraft.trim();
    const feedbackRequest: FeedbackRequest = {
      id: `feedback-${Date.now()}`,
      baseVersionId,
      compareVersionId,
      targetVersionId: compareVersionId,
      lineStart: reviewSelection.lineStart,
      lineEnd: reviewSelection.lineEnd,
      selectedText: reviewSelection.text,
      instruction,
      baseSnapshot: baseText,
      compareSnapshot: compareText,
      createdAt: new Date().toISOString(),
    };
    setIsSubmittingFeedback(true);
    setFeedbackError(null);

    try {
      const revision = await requestFeedbackRevision(feedbackRequest);

      setFeedbackRequests((currentRequests) => [
        ...currentRequests,
        feedbackRequest,
      ]);
      setReviewThreads((currentThreads) => [
        ...currentThreads,
        {
          id: `thread-${feedbackRequest.id}`,
          versionId: compareVersionId,
          feedbackRequestId: feedbackRequest.id,
          lineStart: reviewSelection.lineStart,
          lineEnd: reviewSelection.lineEnd,
          quote: reviewSelection.text,
          instruction,
          replacement: revision.proposedRevision,
          suggestion: revision.rationale,
          status: "open",
        },
      ]);
      clearSelection();
    } catch (error) {
      setFeedbackError(
        error instanceof Error
          ? error.message
          : "Could not generate a targeted revision.",
      );
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const applySuggestion = (thread: ReviewThread) => {
    const previousText = versionDrafts[thread.versionId];

    setVersionDrafts((currentDrafts) => ({
      ...currentDrafts,
      [thread.versionId]: applyThreadSuggestion(
        currentDrafts[thread.versionId],
        thread,
      ),
    }));
    setReviewThreads((currentThreads) =>
      currentThreads.map((currentThread) =>
        currentThread.id === thread.id
          ? { ...currentThread, previousText, status: "applied" }
          : currentThread,
      ),
    );
    void updateFeedbackThreadStatus(thread.feedbackRequestId, {
      previousText,
      status: "applied",
    });
  };

  const undoSuggestion = (thread: ReviewThread) => {
    if (!thread.previousText) {
      return;
    }

    setVersionDrafts((currentDrafts) => ({
      ...currentDrafts,
      [thread.versionId]: thread.previousText!,
    }));
    setReviewThreads((currentThreads) =>
      currentThreads.map((currentThread) =>
        currentThread.id === thread.id
          ? { ...currentThread, previousText: undefined, status: "open" }
          : currentThread,
      ),
    );
    void updateFeedbackThreadStatus(thread.feedbackRequestId, {
      previousText: null,
      status: "open",
    });
  };

  return (
    <main className="min-h-screen bg-[var(--bg)] text-[var(--ink)]">
      <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-[rgba(251,247,236,0.88)] backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <OrchardMark size={28} />
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-base font-semibold text-[var(--ink)]">
                Talent Promo
              </span>
              <span
                className="text-sm italic text-[var(--muted)]"
                style={{ fontFamily: "Instrument Serif, Georgia, serif" }}
              >
                a resume concierge
              </span>
            </div>
          </div>
          <nav className="flex flex-wrap items-center gap-2 text-sm">
            <span className="inline-flex h-8 items-center gap-2 rounded-full border border-[var(--y-100)] bg-[var(--y-50)] px-3 text-xs font-medium text-[var(--y-700)]">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--y-600)]" />
              <strong className="font-semibold">17</strong> of 30 free runs left today
            </span>
            <button
              className="h-8 px-3 text-[var(--ink-3)] transition hover:text-[var(--ink)]"
              type="button"
            >
              How it works
            </button>
            <button
              className="h-8 px-3 text-[var(--ink-3)] transition hover:text-[var(--ink)]"
              type="button"
            >
              Examples
            </button>
          </nav>
        </div>
      </header>

      <StageStrip />

      <section className="border-b border-[var(--line)] bg-[var(--surface-tint)]">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-5 py-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
              Stage 04
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal text-[var(--ink)]">
              Resume{" "}
              <em
                className="font-normal italic text-[var(--y-700)]"
                style={{ fontFamily: "Instrument Serif, Georgia, serif" }}
              >
                diff
              </em>{" "}
              review
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--ink-3)]">
              Choose two versions to compare. Red lines were removed from the
              left version; green lines were added in the right version. Use +
              beside a right-side line, or highlight right-side text, to ask for
              a targeted rewrite.
            </p>
          </div>
          <div className="flex gap-2">
            <SummaryPill count={stats.additions} kind="added" />
            <SummaryPill count={stats.removals} kind="removed" />
          </div>
        </div>
      </section>

      <section className="border-b border-[var(--line)] bg-[var(--surface)]">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div
            className="flex flex-wrap items-center gap-2 text-sm text-[var(--ink-3)]"
            aria-label="Version comparison controls"
          >
            <span className="font-medium text-[var(--ink)]">Compare</span>
            <VersionPicker
              label="From version"
              onChange={(value) => {
                setBaseVersionId(value);
                setReviewSelection(null);
                setFeedbackDraft("");
              }}
              onOpenChange={(open) => setVersionMenu(open ? "base" : null)}
              open={versionMenu === "base"}
              options={versionOptions}
              value={baseVersionId}
            />
            <span className="font-medium text-[var(--ink-3)]">against</span>
            <VersionPicker
              align="right"
              label="To version"
              onChange={(value) => {
                setCompareVersionId(value);
                setReviewSelection(null);
                setFeedbackDraft("");
              }}
              onOpenChange={(open) => setVersionMenu(open ? "compare" : null)}
              open={versionMenu === "compare"}
              options={versionOptions}
              value={compareVersionId}
            />
          </div>
          <button className="inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 text-sm font-medium text-[var(--ink-3)] transition hover:border-[var(--ink-3)] hover:text-[var(--ink)]" type="button">
            <svg
              aria-hidden="true"
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 16 16"
            >
              <path
                d="M2 8a6 6 0 1 0 1.5-4M3.5 1.5v3h3"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.4"
              />
            </svg>
            Regenerate whole resume
          </button>
        </div>
      </section>

      {stats.fullRewrite ? (
        <section className="border-b border-[var(--y-200)] bg-[var(--y-50)]">
          <div className="mx-auto w-full max-w-7xl px-5 py-3 text-sm text-[var(--y-700)]">
            Full rewrite detected. The comparison is showing broad replacement
            rows instead of forcing false line matches.
          </div>
        </section>
      ) : null}

      <section className="mx-auto w-full max-w-7xl px-5 py-5">
        <div className="overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--surface)] shadow-[var(--sh-2)]">
          <div className="flex min-h-14 items-center justify-between border-b border-[var(--line)] bg-[var(--bg-2)] px-5">
            <div>
              <h2 className="font-mono text-sm font-semibold text-[var(--ink)]">
                resume.txt
              </h2>
              <p className="text-xs text-[var(--ink-3)]">
                {baseVersion?.label} to {compareVersion?.label}:{" "}
                {compareVersion?.summary}
              </p>
            </div>
            <div className="text-sm font-medium text-[var(--y-700)]">
              {activeRequestCount === 0 ? (
                "No feedback yet"
              ) : (
                <>
                  {pendingFeedbackCount} pending · {appliedFeedbackCount} used
                </>
              )}
            </div>
          </div>

          <div
            className="max-h-[calc(100vh-18rem)] min-h-[540px] overflow-auto bg-[var(--surface)] font-mono text-sm leading-6"
            onKeyUp={captureGeneratedSelection}
            onMouseUp={captureGeneratedSelection}
            ref={diffRef}
          >
            {sideBySideRows.map((row) => {
              const rowThreads = activeThreads.filter(
                (thread) => thread.lineEnd === row.newLine,
              );
              const leftChanged = row.kind === "changed" || row.kind === "removed";
              const rightChanged = row.kind === "changed" || row.kind === "added";

              return (
                <div key={row.id}>
                  <div className="grid min-w-[1040px] grid-cols-[4rem_minmax(0,1fr)_4rem_2rem_2.5rem_minmax(0,1fr)] border-b border-[var(--line-soft)]">
                    <div
                      className={[
                        "select-none border-r border-[var(--line-soft)] px-2 text-right text-[var(--muted)]",
                        leftChanged ? "bg-[rgba(178,58,42,0.06)]" : "bg-[var(--surface)]",
                      ].join(" ")}
                    >
                      {row.oldLine ?? ""}
                    </div>
                    <div
                      className={[
                        "overflow-x-auto whitespace-pre px-3",
                        leftChanged
                          ? "bg-[rgba(178,58,42,0.06)] text-[#9c3a28]"
                          : "bg-[var(--surface)] text-[var(--ink-2)]",
                      ].join(" ")}
                    >
                      {row.oldText !== undefined ? (
                        leftChanged ? (
                          <del className="decoration-[#b23a2a]/60 decoration-2">
                            {row.oldText || " "}
                          </del>
                        ) : (
                          row.oldText || " "
                        )
                      ) : (
                        " "
                      )}
                    </div>
                    <div
                      className={[
                        "select-none border-x border-[var(--line-soft)] px-2 text-right text-[var(--muted)]",
                        rightChanged
                          ? "bg-[rgba(47,138,79,0.07)]"
                          : "bg-[var(--surface)]",
                      ].join(" ")}
                    >
                      {row.newLine ?? ""}
                    </div>
                    <div
                      className={[
                        "select-none px-2 text-center font-semibold",
                        rightChanged
                          ? "bg-[rgba(47,138,79,0.07)] text-[#1f6b3a]"
                          : "bg-[var(--surface)] text-[var(--muted)]",
                      ].join(" ")}
                    >
                      {rightChanged ? "+" : " "}
                    </div>
                    <div
                      className={[
                        "flex items-center justify-center",
                        rightChanged
                          ? "bg-[rgba(47,138,79,0.07)]"
                          : "bg-[var(--surface)]",
                      ].join(" ")}
                    >
                      {row.newLine ? (
                        <button
                          aria-label={`Add targeted feedback for compare line ${row.newLine}`}
                          className="h-5 w-5 rounded border border-[var(--y-200)] bg-[var(--surface)] text-xs font-semibold text-[var(--y-700)] transition hover:border-[var(--y-500)] hover:bg-[var(--y-50)]"
                          title={`Add targeted feedback for compare line ${row.newLine}`}
                          type="button"
                          onClick={(event) =>
                            openLineFeedback(row.newLine!, row.newText ?? "", event)
                          }
                        >
                          +
                        </button>
                      ) : null}
                    </div>
                    <div
                      className={[
                        "overflow-x-auto whitespace-pre px-3",
                        rightChanged
                          ? "bg-[rgba(47,138,79,0.07)] text-[var(--ink)]"
                          : "bg-[var(--surface)] text-[var(--ink-2)]",
                      ].join(" ")}
                      data-review-line={row.newLine}
                      data-review-version={row.newLine ? compareVersionId : undefined}
                    >
                      {row.newText !== undefined ? row.newText || " " : " "}
                    </div>
                  </div>

                  {rowThreads.map((thread) => (
                    <div
                      className="grid min-w-[1040px] grid-cols-[4rem_minmax(0,1fr)_4rem_2rem_2.5rem_minmax(0,1fr)] border-b border-[var(--line-soft)] bg-[var(--surface-tint)]"
                      key={thread.id}
                    >
                      <div className="col-span-2 border-r border-[var(--line-soft)]" />
                      <div
                        className={[
                          "col-span-4 p-3",
                          thread.status === "applied"
                            ? "border-l-4 border-[var(--green)]"
                            : "border-l-4 border-[var(--y-500)]",
                        ].join(" ")}
                      >
                        {thread.status === "applied" ? (
                          <div className="flex max-w-3xl items-center justify-between gap-3 rounded-lg border border-[rgba(47,138,79,0.25)] bg-[rgba(47,138,79,0.08)] px-3 py-2 font-sans text-sm text-[var(--ink-2)]">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 font-semibold text-[var(--ink)]">
                                <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-[var(--green)] text-xs text-white">
                                  ✓
                                </span>
                                Used revised text on{" "}
                                {lineRangeLabel(thread.lineStart, thread.lineEnd)}
                              </div>
                              <div className="mt-0.5 text-xs text-[var(--ink-3)]">
                                The new revision landed in {compareVersion?.label}; the
                                thread is collapsed so the diff stays readable.
                              </div>
                            </div>
                            <button
                              className="shrink-0 rounded-lg border border-[rgba(47,138,79,0.35)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--green)] transition hover:border-[var(--green)]"
                              type="button"
                              onClick={() => undoSuggestion(thread)}
                            >
                              Undo
                            </button>
                          </div>
                        ) : (
                          <div className="max-w-3xl rounded-lg border border-[var(--line)] bg-[var(--surface)] p-3 font-sans text-sm leading-6 shadow-[var(--sh-1)]">
                            <div className="mb-2 flex items-center justify-between gap-3">
                              <span className="font-semibold text-[var(--ink)]">
                                Targeted revision for{" "}
                                {lineRangeLabel(thread.lineStart, thread.lineEnd)}
                              </span>
                              <span className="text-xs uppercase tracking-[0.12em] text-[var(--muted)]">
                                pending
                              </span>
                            </div>
                            <div className="mb-3 grid gap-2">
                              <div>
                                <div className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">
                                  Current generated text
                                </div>
                                <blockquote className="border-l-2 border-[var(--line)] pl-2 text-[var(--ink-3)]">
                                  {thread.quote}
                                </blockquote>
                              </div>
                              <div>
                                <div className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">
                                  Your feedback
                                </div>
                                <p>{thread.instruction}</p>
                              </div>
                              <div>
                                <div className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--green)]">
                                  New proposed revision
                                </div>
                                <div className="rounded-md border border-[rgba(47,138,79,0.25)] bg-[rgba(47,138,79,0.08)] px-3 py-2 text-[var(--ink)]">
                                  {thread.replacement || "Remove this text."}
                                </div>
                              </div>
                              <p className="text-xs text-[var(--ink-3)]">
                                {thread.suggestion}
                              </p>
                            </div>
                            <button
                              className="mt-3 rounded-lg border border-[var(--ink)] bg-[var(--ink)] px-3 py-1.5 text-sm font-semibold text-[var(--bg)] transition hover:bg-black"
                              type="button"
                              onClick={() => applySuggestion(thread)}
                            >
                              Use this revision
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {reviewSelection ? (
        <form
          className="fixed z-40 grid w-[360px] gap-3 rounded-lg border border-[var(--line)] bg-[var(--surface)] p-3 shadow-[0_20px_50px_-16px_rgba(80,60,0,0.22)]"
          onSubmit={(event) => {
            event.preventDefault();
            submitFeedback();
          }}
          style={{
            left: reviewSelection.left,
            top: reviewSelection.top,
          }}
        >
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">
              Comment on {lineRangeLabel(reviewSelection.lineStart, reviewSelection.lineEnd)}
            </div>
            <div className="mt-1 max-h-16 overflow-auto border-l-2 border-[var(--y-200)] pl-2 text-sm text-[var(--ink-3)]">
              {reviewSelection.text}
            </div>
          </div>
          <textarea
            className="min-h-20 resize-none rounded-lg border border-[var(--line)] bg-[var(--surface-tint)] p-2 text-sm outline-none transition focus:border-[var(--y-500)] focus:ring-4 focus:ring-[rgba(239,188,34,0.18)]"
            value={feedbackDraft}
            onChange={(event) => setFeedbackDraft(event.target.value)}
            placeholder="Ask for a targeted revision"
          />
          {feedbackError ? (
            <div className="rounded-lg border border-[#b23a2a]/25 bg-[#b23a2a]/5 px-3 py-2 text-sm text-[#9c3a28]">
              {feedbackError}
            </div>
          ) : null}
          <div className="flex justify-end gap-2">
            <button
              className="rounded-lg border border-[var(--line)] px-3 py-1.5 text-sm font-medium text-[var(--ink-3)] transition hover:border-[var(--ink-3)] hover:text-[var(--ink)]"
              type="button"
              onClick={clearSelection}
            >
              Cancel
            </button>
            <button
              className="rounded-lg border border-[var(--ink)] bg-[var(--ink)] px-3 py-1.5 text-sm font-semibold text-[var(--bg)] transition enabled:hover:bg-black disabled:cursor-not-allowed disabled:border-[var(--line)] disabled:bg-[var(--line-soft)] disabled:text-[var(--muted)]"
              disabled={!canSubmitFeedback}
              type="submit"
            >
              {isSubmittingFeedback ? "Generating..." : "Add feedback"}
            </button>
          </div>
        </form>
      ) : null}
    </main>
  );
}
