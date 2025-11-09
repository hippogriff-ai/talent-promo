"use client";

import { useState } from "react";
import type { ParsedResume } from "@/app/types/resume";
import DOMPurify from "dompurify";

interface ResumeViewerProps {
  resume: ParsedResume;
  onUpdate?: (resume: ParsedResume) => void;
}

type ViewMode = "structured" | "json";

export default function ResumeViewer({ resume, onUpdate }: ResumeViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("structured");
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(resume, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const toggleSection = (section: string) => {
    const newCollapsed = new Set(collapsed);
    if (newCollapsed.has(section)) {
      newCollapsed.delete(section);
    } else {
      newCollapsed.add(section);
    }
    setCollapsed(newCollapsed);
  };

  const sanitize = (text: string) => {
    return DOMPurify.sanitize(text, { ALLOWED_TAGS: [] });
  };

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold">Parsed Resume</h3>
          <div className="flex gap-2">
            <button
              onClick={() => setViewMode("structured")}
              className={`px-3 py-1 rounded ${
                viewMode === "structured"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              Structured
            </button>
            <button
              onClick={() => setViewMode("json")}
              className={`px-3 py-1 rounded ${
                viewMode === "json"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              JSON
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between text-sm">
          <div className="text-gray-600">
            Confidence: {((resume.metadata.confidence || 0) * 100).toFixed(0)}%
          </div>
          <button
            onClick={handleCopy}
            className="flex items-center gap-2 px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-gray-700"
          >
            {copied ? (
              <>
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Copied!
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
                Copy JSON
              </>
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-6 max-h-[600px] overflow-y-auto">
        {viewMode === "structured" ? (
          <div className="space-y-6">
            {/* Personal Info */}
            <Section
              title="Personal Information"
              collapsed={collapsed.has("personal")}
              onToggle={() => toggleSection("personal")}
            >
              <div className="grid grid-cols-2 gap-4 text-sm">
                <InfoItem label="Name" value={sanitize(resume.personalInfo.name)} />
                <InfoItem label="Email" value={resume.personalInfo.email} />
                <InfoItem label="Phone" value={resume.personalInfo.phone} />
                <InfoItem label="LinkedIn" value={resume.personalInfo.linkedinUrl} link />
              </div>
            </Section>

            {/* Summary */}
            {resume.summary && (
              <Section
                title="Summary"
                collapsed={collapsed.has("summary")}
                onToggle={() => toggleSection("summary")}
              >
                <p className="text-sm text-gray-700">{sanitize(resume.summary)}</p>
              </Section>
            )}

            {/* Work Experience */}
            {resume.workExperience.length > 0 && (
              <Section
                title={`Work Experience (${resume.workExperience.length})`}
                collapsed={collapsed.has("experience")}
                onToggle={() => toggleSection("experience")}
              >
                <div className="space-y-4">
                  {resume.workExperience.map((exp) => (
                    <div key={exp.id} className="border-l-2 border-blue-500 pl-4">
                      <h4 className="font-semibold">{sanitize(exp.position)}</h4>
                      <p className="text-sm text-gray-600">{sanitize(exp.company)}</p>
                      <p className="text-xs text-gray-500">
                        {exp.startDate} - {exp.endDate || "Present"}
                      </p>
                      {exp.achievements && exp.achievements.length > 0 && (
                        <ul className="mt-2 space-y-1 text-sm">
                          {exp.achievements.map((achievement, idx) => (
                            <li key={idx} className="text-gray-700">
                              • {sanitize(achievement)}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Education */}
            {resume.education.length > 0 && (
              <Section
                title={`Education (${resume.education.length})`}
                collapsed={collapsed.has("education")}
                onToggle={() => toggleSection("education")}
              >
                <div className="space-y-4">
                  {resume.education.map((edu) => (
                    <div key={edu.id} className="border-l-2 border-green-500 pl-4">
                      <h4 className="font-semibold">{sanitize(edu.degree)}</h4>
                      <p className="text-sm text-gray-600">{sanitize(edu.institution)}</p>
                      {edu.field && (
                        <p className="text-sm text-gray-600">{sanitize(edu.field)}</p>
                      )}
                      {(edu.startDate || edu.endDate) && (
                        <p className="text-xs text-gray-500">
                          {edu.startDate} - {edu.endDate}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Skills */}
            {resume.skills.length > 0 && (
              <Section
                title={`Skills (${resume.skills.length})`}
                collapsed={collapsed.has("skills")}
                onToggle={() => toggleSection("skills")}
              >
                <div className="flex flex-wrap gap-2">
                  {resume.skills.map((skill, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                    >
                      {sanitize(skill.name)}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {/* Certifications */}
            {resume.certifications.length > 0 && (
              <Section
                title={`Certifications (${resume.certifications.length})`}
                collapsed={collapsed.has("certifications")}
                onToggle={() => toggleSection("certifications")}
              >
                <ul className="space-y-2 text-sm">
                  {resume.certifications.map((cert) => (
                    <li key={cert.id} className="flex items-start">
                      <span className="text-yellow-500 mr-2">🏆</span>
                      <div>
                        <p className="font-medium">{sanitize(cert.name)}</p>
                        {cert.issuer && (
                          <p className="text-gray-600">Issued by: {sanitize(cert.issuer)}</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Projects */}
            {resume.projects.length > 0 && (
              <Section
                title={`Projects (${resume.projects.length})`}
                collapsed={collapsed.has("projects")}
                onToggle={() => toggleSection("projects")}
              >
                <div className="space-y-3">
                  {resume.projects.map((project) => (
                    <div key={project.id}>
                      <h4 className="font-semibold text-sm">{sanitize(project.name)}</h4>
                      <p className="text-sm text-gray-600">{sanitize(project.description)}</p>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Languages */}
            {resume.languages.length > 0 && (
              <Section
                title={`Languages (${resume.languages.length})`}
                collapsed={collapsed.has("languages")}
                onToggle={() => toggleSection("languages")}
              >
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {resume.languages.map((lang, idx) => (
                    <div key={idx}>
                      <span className="font-medium">{sanitize(lang.name)}</span>
                      <span className="text-gray-600"> - {lang.proficiency}</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </div>
        ) : (
          <pre className="text-xs bg-gray-50 p-4 rounded overflow-x-auto">
            {JSON.stringify(resume, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
  collapsed,
  onToggle,
}: {
  title: string;
  children: React.ReactNode;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between text-left transition-colors"
      >
        <h4 className="font-semibold text-gray-900">{title}</h4>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${
            collapsed ? "" : "transform rotate-180"
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {!collapsed && <div className="p-4">{children}</div>}
    </div>
  );
}

function InfoItem({
  label,
  value,
  link,
}: {
  label: string;
  value?: string;
  link?: boolean;
}) {
  if (!value) return null;

  return (
    <div>
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium text-gray-900">
        {link ? (
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            {value}
          </a>
        ) : (
          value
        )}
      </dd>
    </div>
  );
}
