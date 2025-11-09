/**
 * Comprehensive Resume Data Schema
 * Defines the structure for parsed resume data
 */

export interface PersonalInfo {
  name: string;
  email?: string;
  phone?: string;
  location?: {
    city?: string;
    state?: string;
    country?: string;
    postalCode?: string;
  };
  linkedinUrl?: string;
  portfolioUrl?: string;
  githubUrl?: string;
  otherUrls?: string[];
}

export interface WorkExperience {
  id: string;
  company: string;
  position: string;
  location?: string;
  startDate: string;
  endDate?: string; // undefined means current
  isCurrent?: boolean;
  description?: string;
  achievements?: string[];
  technologies?: string[];
}

export interface Education {
  id: string;
  institution: string;
  degree: string;
  field?: string;
  location?: string;
  startDate?: string;
  endDate?: string;
  gpa?: number;
  honors?: string[];
  description?: string;
}

export interface Skill {
  name: string;
  category?: string; // e.g., "Technical", "Soft Skills", "Languages"
  level?: "Beginner" | "Intermediate" | "Advanced" | "Expert";
  yearsOfExperience?: number;
}

export interface Certification {
  id: string;
  name: string;
  issuer: string;
  issueDate?: string;
  expiryDate?: string;
  credentialId?: string;
  credentialUrl?: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  role?: string;
  startDate?: string;
  endDate?: string;
  url?: string;
  technologies?: string[];
  achievements?: string[];
}

export interface Language {
  name: string;
  proficiency: "Native" | "Fluent" | "Professional" | "Limited" | "Basic";
}

export interface Reference {
  name: string;
  relationship?: string;
  company?: string;
  email?: string;
  phone?: string;
}

export interface ParsedResume {
  id: string;
  personalInfo: PersonalInfo;
  summary?: string;
  workExperience: WorkExperience[];
  education: Education[];
  skills: Skill[];
  certifications: Certification[];
  projects: Project[];
  languages: Language[];
  references: Reference[];
  rawText?: string; // Original extracted text
  metadata: {
    fileName: string;
    fileSize: number;
    fileType: string;
    parsedDate: string;
    parseVersion: string; // Schema version for migration purposes
    confidence?: number; // Overall parsing confidence 0-1
  };
}

export interface ParseResult {
  success: boolean;
  data?: ParsedResume;
  error?: string;
  warnings?: string[];
}
