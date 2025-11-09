/**
 * Job Posting Data Schema
 * Defines the structure for job posting data retrieved from various platforms
 */

export type JobType = "Full-time" | "Part-time" | "Contract" | "Internship" | "Temporary";
export type WorkLocation = "Remote" | "Hybrid" | "Onsite";
export type ExperienceLevel = "Entry Level" | "Mid Level" | "Senior Level" | "Lead" | "Executive";

export interface CompanyInfo {
  name: string;
  industry?: string;
  size?: string; // e.g., "50-200 employees"
  website?: string;
  logo?: string;
  description?: string;
}

export interface Location {
  city?: string;
  state?: string;
  country?: string;
  remote?: boolean;
  hybrid?: boolean;
  specificLocation?: string; // Full location string
}

export interface SalaryRange {
  min?: number;
  max?: number;
  currency: string;
  period: "Hour" | "Year" | "Month" | "Week";
  displayText?: string; // e.g., "$100k - $150k/year"
}

export interface Requirement {
  text: string;
  required: boolean; // true for required, false for preferred
  category?: "education" | "experience" | "skill" | "certification" | "other";
}

export interface Benefit {
  category?: "health" | "financial" | "time-off" | "professional-development" | "other";
  description: string;
}

export interface ApplicationInfo {
  method?: "external" | "internal" | "email";
  url?: string;
  email?: string;
  deadline?: string;
  customInstructions?: string;
}

export interface JobPosting {
  id: string;
  title: string;
  jobId?: string; // Platform-specific job ID
  company: CompanyInfo;
  location: Location;
  workLocation: WorkLocation;
  jobType: JobType;
  experienceLevel?: ExperienceLevel;
  description: string;
  responsibilities?: string[];
  requirements: Requirement[];
  preferredQualifications?: string[];
  benefits?: Benefit[];
  salaryRange?: SalaryRange;
  postedDate?: string;
  closingDate?: string;
  applicationInfo?: ApplicationInfo;
  sourceUrl: string;
  platform: "LinkedIn" | "Indeed" | "Glassdoor" | "AngelList" | "Company" | "Other";
  metadata: {
    retrievedDate: string;
    retrievalMethod: string; // "scraper" | "api"
    dataQuality?: number; // 0-1 confidence score
    lastUpdated?: string;
  };
}

export interface JobRetrievalResult {
  success: boolean;
  data?: JobPosting;
  error?: string;
  warnings?: string[];
}

export interface BatchJobRetrievalResult {
  results: JobRetrievalResult[];
  summary: {
    total: number;
    successful: number;
    failed: number;
    warnings: number;
  };
}
