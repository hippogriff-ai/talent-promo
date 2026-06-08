// Shared types between frontend and backend

export interface ResumeDoc {
  id: string;
  sections: Section[];
}

export interface Section {
  id: string;
  title: string;
  roles?: Role[];
}

export interface Role {
  id: string;
  title: string;
  company: string;
  bullets: Bullet[];
}

export interface Bullet {
  id: string;
  text: string;
  targetPath: string;
}

export type ResumeUnitKind =
  | "header"
  | "header_name"
  | "contact"
  | "section"
  | "role"
  | "role_meta"
  | "paragraph"
  | "bullet"
  | "item"
  | "skill";

export interface ResumeUnit {
  id: string;
  kind: ResumeUnitKind;
  label: string;
  text?: string;
  title?: string;
  children?: ResumeUnit[];
  metadata?: Record<string, unknown>;
}

export interface ResumeDocument {
  documentId: string;
  revisionId: string;
  schemaVersion: number;
  createdAt: string;
  updatedAt: string;
  sourceHtmlHash?: string;
  sections: ResumeUnit[];
}

export interface ResumeMapUnit {
  id: string;
  kind: ResumeUnitKind;
  label: string;
  pathLabel: string;
  parentId?: string;
  wordCount: number;
  textPreview: string;
  childIds: string[];
  metadata?: Record<string, unknown>;
}

export interface ResumeMap {
  documentId: string;
  revisionId: string;
  units: ResumeMapUnit[];
}

export interface ResumeAddress {
  documentId: string;
  revisionId: string;
  unitId: string;
  pathLabel: string;
}

export interface EditIntent {
  userMessage: string;
  selectedText?: string;
  action?: string;
  currentDocumentRevisionId?: string;
}

export interface EditPlanAssertion {
  id: string;
  description: string;
  status: "pending" | "passed" | "needs_review" | "failed";
}

export interface EditPlanTodo {
  id: string;
  label: string;
  status: "pending" | "done" | "failed";
}

export interface EditPlan {
  id: string;
  goal: string;
  targetUnitId: string;
  targetLabel: string;
  scope: "single_unit";
  assertions: EditPlanAssertion[];
  todos: EditPlanTodo[];
}

export interface PatchOperation {
  targetUnitId: string;
  format: "search_replace";
  text: string;
}

export interface VerificationCheck {
  id: string;
  passed: boolean;
  reason: string;
}

export interface VerificationReport {
  passed: boolean;
  checks: VerificationCheck[];
  evidence: string;
  summary: string;
}

export interface GitRevisionMetadata {
  sha: string;
  message: string;
}

export interface RevisionSnapshot {
  success: boolean;
  documentId: string;
  revisionId: string;
  documentRevisionId: string;
  targetUnit: {
    id: string;
    kind: ResumeUnitKind;
    label: string;
    text: string;
    textPreview: string;
  };
  editPlan: EditPlan;
  patch: string;
  proposedText: string;
  verification: VerificationReport;
  canApply: boolean;
  overrideRequired?: boolean;
  error?: string;
  candidates?: ResumeMapUnit[];
}
