/**
 * TypeScript interfaces for AI safety guardrails validation results.
 *
 * These types mirror the Python guardrails module output and are used
 * to display warnings about bias, PII, and other safety concerns.
 */

/**
 * Bias flag detected in resume content.
 */
export interface BiasFlag {
  /** Category of bias (e.g., "age", "gender", "race_ethnicity") */
  category: string;
  /** The specific term that triggered the flag */
  term: string;
  /** Surrounding context where the term was found */
  context: string;
  /** Severity level ("warning" or "block") */
  severity: string;
  /** Suggested alternative term, if available */
  suggestion: string | null;
  /** Human-readable warning message */
  message: string;
}

/**
 * PII (Personally Identifiable Information) warning.
 */
export interface PIIWarning {
  /** Type of PII detected (e.g., "ssn", "credit_card") */
  type: string;
  /** Partially masked value for display */
  masked_value: string;
  /** Severity level ("high" or "medium") */
  severity: string;
  /** Human-readable warning message */
  message: string;
}

/**
 * Ungrounded claim detected in generated resume content.
 */
export interface UngroundedClaim {
  /** The claim text that may not be supported */
  claim: string;
  /** Type of claim (e.g., "quantified", "company", "title") */
  type: string;
  /** Confidence that this claim is ungrounded (0-1) */
  confidence: number;
  /** Additional context about the claim */
  context: string;
  /** Human-readable verification message */
  message: string;
}

/**
 * Combined validation results from guardrails.
 */
export interface ValidationResults {
  /** Whether all critical validations passed */
  passed: boolean;
  /** General warnings (non-blocking issues) */
  warnings: string[];
  /** Detected bias indicators in the content */
  bias_flags: BiasFlag[];
  /** Detected sensitive PII in the content */
  pii_warnings: PIIWarning[];
  /** Claims that may not be supported by the source profile */
  ungrounded_claims: UngroundedClaim[];
  /** Whether the content was sanitized (problematic patterns removed) */
  sanitized: boolean;
}

/**
 * Category display information for grouping bias flags.
 */
export interface BiasCategoryInfo {
  /** Internal category key */
  key: string;
  /** Human-readable label */
  label: string;
  /** Description of this bias category */
  description: string;
  /** Icon to display (optional) */
  icon?: string;
}

/**
 * Mapping of bias category keys to display info.
 */
export const BIAS_CATEGORIES: Record<string, BiasCategoryInfo> = {
  age: {
    key: "age",
    label: "Age Bias",
    description: "Language that may discriminate based on age",
  },
  gender: {
    key: "gender",
    label: "Gender Bias",
    description: "Gendered language that could be more inclusive",
  },
  race_ethnicity: {
    key: "race_ethnicity",
    label: "Race/Ethnicity Bias",
    description: "Language that may be discriminatory",
  },
  disability: {
    key: "disability",
    label: "Disability Bias",
    description: "Language that may exclude disabled candidates",
  },
  religion: {
    key: "religion",
    label: "Religious Bias",
    description: "Language with religious connotations",
  },
  nationality: {
    key: "nationality",
    label: "Nationality Bias",
    description: "Language that may discriminate by national origin",
  },
};

/**
 * PII type display information.
 */
export const PII_TYPES: Record<string, string> = {
  ssn: "Social Security Number",
  credit_card: "Credit Card Number",
  bank_account: "Bank Account Number",
  drivers_license: "Driver's License",
  passport: "Passport Number",
  date_of_birth: "Date of Birth",
  ip_address: "IP Address",
};

/**
 * Claim type display information.
 */
export const CLAIM_TYPES: Record<string, string> = {
  quantified: "Quantified Metric",
  company: "Company Name",
  title: "Job Title",
  skill: "Technical Skill",
  timeframe: "Timeframe",
};
