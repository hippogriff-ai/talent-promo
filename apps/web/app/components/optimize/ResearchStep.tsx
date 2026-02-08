"use client";

import { useState, useEffect, useRef } from "react";
import {
  UserProfile,
  JobPosting,
  ResearchFindings,
  GapAnalysis,
  WorkflowStep,
} from "../../hooks/useWorkflow";

/** Map LLM importance values ("critical"/"important"/"nice-to-have") to display styles */
function importanceStyle(importance: string | undefined) {
  const v = (importance || "").toLowerCase();
  if (v === "critical" || v === "high") return { bg: "bg-red-100 text-red-700", badge: "bg-red-200 text-red-700", border: "bg-red-50 border border-red-200", label: v };
  if (v === "important" || v === "medium") return { bg: "bg-yellow-100 text-yellow-700", badge: "bg-yellow-200 text-yellow-700", border: "bg-yellow-50 border border-yellow-200", label: v };
  return { bg: "bg-gray-100 text-gray-600", badge: "bg-gray-200 text-gray-600", border: "bg-gray-50 border border-gray-200", label: v };
}
import { ProfileEditorModal } from "./ProfileEditorModal";

interface ProgressMessage {
  timestamp: string;
  phase: string;
  message: string;
  detail: string;
}

interface ResearchStepProps {
  currentStep: WorkflowStep;
  userProfile: UserProfile | null;
  jobPosting: JobPosting | null;
  // Raw markdown from EXA for display/editing
  profileMarkdown: string | null;
  jobMarkdown: string | null;
  research: ResearchFindings | null;
  gapAnalysis: GapAnalysis | null;
  progressMessages?: ProgressMessage[];
}

// Full research view for modal
export function ResearchFullView({ research, gapAnalysis }: { research: ResearchFindings; gapAnalysis?: GapAnalysis | null }) {
  return (
    <div className="space-y-6">
      {/* Company Overview */}
      {research.company_overview && (
        <div id="section-company-overview">
          <h5 className="font-semibold text-gray-800 mb-2">Company Overview</h5>
          <p className="text-gray-600 text-sm whitespace-pre-wrap">{research.company_overview}</p>
        </div>
      )}

      {/* Company Culture */}
      {research.company_culture && (
        <div id="section-company-culture">
          <h5 className="font-semibold text-gray-800 mb-2">Company Culture</h5>
          <p className="text-gray-600 text-sm whitespace-pre-wrap">{research.company_culture}</p>
        </div>
      )}

      {/* Company Values */}
      {research.company_values && research.company_values.length > 0 && (
        <div id="section-company-values">
          <h5 className="font-semibold text-gray-800 mb-2">Company Values</h5>
          <div className="flex flex-wrap gap-2">
            {research.company_values.map((value, idx) => (
              <span
                key={idx}
                className="px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full"
              >
                {value}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tech Stack Details */}
      {research.tech_stack_details && research.tech_stack_details.length > 0 && (
        <div id="section-tech-stack">
          <h5 className="font-semibold text-gray-800 mb-2">Tech Stack Details</h5>
          <div className="space-y-2">
            {research.tech_stack_details.map((tech, idx) => (
              <div key={idx} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900">{tech.technology}</span>
                  {tech.importance && (
                    <span className={`px-2 py-0.5 text-xs rounded ${importanceStyle(tech.importance).bg}`}>
                      {tech.importance}
                    </span>
                  )}
                </div>
                {tech.usage && (
                  <p className="text-sm text-gray-600 mt-1">{tech.usage}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Similar Profiles */}
      {research.similar_profiles && research.similar_profiles.length > 0 && (
        <div id="section-similar-profiles">
          <h5 className="font-semibold text-gray-800 mb-2">Similar Successful Profiles</h5>
          <div className="space-y-4">
            {research.similar_profiles.map((profile, idx) => (
              <div key={idx} className="border-l-2 border-blue-200 pl-3 bg-blue-50/30 py-2 rounded-r">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{profile.name}</p>
                    <p className="text-sm text-gray-600">{profile.headline}</p>
                    {profile.current_company && (
                      <p className="text-xs text-gray-500 mt-0.5">Currently at: {profile.current_company}</p>
                    )}
                  </div>
                  {profile.url && (
                    <a
                      href={profile.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 text-xs flex items-center"
                    >
                      View Profile
                      <svg className="w-3 h-3 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  )}
                </div>
                {profile.key_skills && profile.key_skills.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {profile.key_skills.map((skill, i) => (
                      <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">
                        {skill}
                      </span>
                    ))}
                  </div>
                )}
                {profile.experience_highlights && profile.experience_highlights.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs text-gray-500 font-medium">Key Accomplishments:</p>
                    <ul className="text-xs text-gray-600 mt-1 space-y-0.5">
                      {profile.experience_highlights.slice(0, 3).map((highlight, i) => (
                        <li key={i} className="flex items-start">
                          <span className="text-green-500 mr-1">✓</span>
                          {highlight}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hiring Patterns */}
      {research.hiring_patterns && (
        <div id="section-hiring-patterns">
          <h5 className="font-semibold text-gray-800 mb-2">Hiring Patterns</h5>
          <p className="text-gray-600 text-sm whitespace-pre-wrap">{research.hiring_patterns}</p>
        </div>
      )}

      {/* Industry Trends */}
      {research.industry_trends && research.industry_trends.length > 0 && (
        <div id="section-industry-trends">
          <h5 className="font-semibold text-gray-800 mb-2">Industry Trends</h5>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            {research.industry_trends.map((trend, idx) => (
              <li key={idx}>{trend}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Company News */}
      {research.company_news && research.company_news.length > 0 && (
        <div id="section-company-news">
          <h5 className="font-semibold text-gray-800 mb-2">Recent Company News</h5>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            {research.company_news.map((news, idx) => (
              <li key={idx}>{news}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Hiring Criteria */}
      {research.hiring_criteria && (
        <div id="section-hiring-criteria" className="bg-amber-50 rounded-lg p-4 border border-amber-200">
          <h5 className="font-semibold text-amber-800 mb-3 flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Hiring Criteria
          </h5>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {research.hiring_criteria.must_haves && research.hiring_criteria.must_haves.length > 0 && (
              <div>
                <p className="text-sm font-medium text-red-700 mb-1">Must-Haves</p>
                <ul className="text-sm text-gray-600 space-y-1">
                  {research.hiring_criteria.must_haves.map((item, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="text-red-500 mr-2">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {research.hiring_criteria.preferred && research.hiring_criteria.preferred.length > 0 && (
              <div>
                <p className="text-sm font-medium text-amber-700 mb-1">Preferred</p>
                <ul className="text-sm text-gray-600 space-y-1">
                  {research.hiring_criteria.preferred.map((item, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="text-amber-500 mr-2">★</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          {((research.hiring_criteria.keywords && research.hiring_criteria.keywords.length > 0) ||
            (research.hiring_criteria.ats_keywords && research.hiring_criteria.ats_keywords.length > 0)) && (
            <div className="mt-3 pt-3 border-t border-amber-200">
              <p className="text-sm font-medium text-amber-700 mb-2">Keywords for ATS Optimization</p>
              <div className="flex flex-wrap gap-1">
                {[...(research.hiring_criteria.keywords || []), ...(research.hiring_criteria.ats_keywords || [])].map((kw, idx) => (
                  <span key={idx} className="px-2 py-0.5 bg-amber-100 text-amber-800 text-xs rounded">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Ideal Profile */}
      {research.ideal_profile && (
        <div id="section-ideal-profile" className="bg-green-50 rounded-lg p-4 border border-green-200">
          <h5 className="font-semibold text-green-800 mb-3 flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Ideal Candidate Profile
          </h5>

          {research.ideal_profile.headline && (
            <div className="mb-3">
              <p className="text-sm font-medium text-green-700">Recommended Headline</p>
              <p className="text-sm text-gray-700 bg-white rounded px-3 py-2 mt-1 border border-green-200">
                {research.ideal_profile.headline}
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {research.ideal_profile.summary_focus && research.ideal_profile.summary_focus.length > 0 && (
              <div>
                <p className="text-sm font-medium text-green-700 mb-1">Summary Focus Areas</p>
                <ul className="text-sm text-gray-600 space-y-1">
                  {research.ideal_profile.summary_focus.map((item, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="text-green-500 mr-2">→</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {research.ideal_profile.experience_emphasis && research.ideal_profile.experience_emphasis.length > 0 && (
              <div>
                <p className="text-sm font-medium text-green-700 mb-1">Experience to Emphasize</p>
                <ul className="text-sm text-gray-600 space-y-1">
                  {research.ideal_profile.experience_emphasis.map((item, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="text-green-500 mr-2">→</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {research.ideal_profile.skills_priority && research.ideal_profile.skills_priority.length > 0 && (
            <div className="mt-3">
              <p className="text-sm font-medium text-green-700 mb-1">Priority Skills</p>
              <div className="flex flex-wrap gap-1">
                {research.ideal_profile.skills_priority.map((skill, idx) => (
                  <span key={idx} className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {research.ideal_profile.differentiators && research.ideal_profile.differentiators.length > 0 && (
            <div className="mt-3 pt-3 border-t border-green-200">
              <p className="text-sm font-medium text-green-700 mb-1">Differentiators (What Makes You Stand Out)</p>
              <ul className="text-sm text-gray-600 space-y-1">
                {research.ideal_profile.differentiators.map((item, idx) => (
                  <li key={idx} className="flex items-start">
                    <span className="text-green-500 mr-2">✨</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* === Gap Analysis Details === */}
      {gapAnalysis && (
        <>
          <hr className="border-gray-200" />
          <h4 id="section-gap-analysis" className="text-base font-semibold text-gray-900 flex items-center">
            <svg className="w-5 h-5 mr-2 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Gap Analysis
          </h4>

          {/* Strengths */}
          {gapAnalysis.strengths && gapAnalysis.strengths.length > 0 && (
            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <h5 className="font-semibold text-green-800 mb-2">Strengths ({gapAnalysis.strengths.length})</h5>
              <ul className="text-sm text-gray-700 space-y-2">
                {gapAnalysis.strengths.map((s, idx) => (
                  <li key={idx} className="flex items-start">
                    <span className="text-green-500 mr-2 mt-0.5 flex-shrink-0">✓</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Gaps */}
          {gapAnalysis.gaps && gapAnalysis.gaps.length > 0 && (
            <div className="bg-amber-50 rounded-lg p-4 border border-amber-200">
              <h5 className="font-semibold text-amber-800 mb-2">Gaps to Address ({gapAnalysis.gaps.length})</h5>
              <ul className="text-sm text-gray-700 space-y-2">
                {gapAnalysis.gaps.map((g, idx) => (
                  <li key={idx} className="flex items-start">
                    <span className="text-amber-500 mr-2 mt-0.5 flex-shrink-0">!</span>
                    <span>{g}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommended Emphasis */}
          {gapAnalysis.recommended_emphasis && gapAnalysis.recommended_emphasis.length > 0 && (
            <div>
              <h5 className="font-semibold text-gray-800 mb-2">Recommended Emphasis</h5>
              <ul className="text-sm text-gray-600 space-y-2">
                {gapAnalysis.recommended_emphasis.map((item, idx) => (
                  <li key={idx} className="flex items-start bg-blue-50 rounded-lg p-3 border border-blue-100">
                    <span className="text-blue-500 mr-2 mt-0.5 flex-shrink-0 font-bold">{idx + 1}.</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Transferable Skills */}
          {gapAnalysis.transferable_skills && gapAnalysis.transferable_skills.length > 0 && (
            <div>
              <h5 className="font-semibold text-gray-800 mb-2">Transferable Skills</h5>
              <ul className="text-sm text-gray-600 space-y-2">
                {gapAnalysis.transferable_skills.map((skill, idx) => (
                  <li key={idx} className="flex items-start">
                    <span className="text-green-500 mr-2 mt-0.5 flex-shrink-0">→</span>
                    <span>{skill}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Keywords to Include */}
          {gapAnalysis.keywords_to_include && gapAnalysis.keywords_to_include.length > 0 && (
            <div>
              <h5 className="font-semibold text-gray-800 mb-2">Keywords to Include ({gapAnalysis.keywords_to_include.length})</h5>
              <div className="flex flex-wrap gap-2">
                {gapAnalysis.keywords_to_include.map((kw, idx) => (
                  <span key={idx} className="px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Potential Concerns */}
          {gapAnalysis.potential_concerns && gapAnalysis.potential_concerns.length > 0 && (
            <div>
              <h5 className="font-semibold text-gray-800 mb-2">Potential Concerns &amp; How to Address</h5>
              <div className="space-y-2">
                {gapAnalysis.potential_concerns.map((concern, idx) => (
                  <div key={idx} className="bg-orange-50 rounded-lg p-3 border border-orange-200 text-sm text-gray-700">
                    {typeof concern === 'string'
                      ? concern
                      : `${(concern as { concern?: string }).concern || ''}${(concern as { mitigation?: string }).mitigation ? ' — ' + (concern as { mitigation?: string }).mitigation : ''}`}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Research modal component
export function ResearchModal({
  isOpen,
  onClose,
  research,
  gapAnalysis,
  scrollToSection,
}: {
  isOpen: boolean;
  onClose: () => void;
  research: ResearchFindings | null;
  gapAnalysis?: GapAnalysis | null;
  scrollToSection?: string | null;
}) {
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && scrollToSection && contentRef.current) {
      // Wait for render, then scroll to section
      const timer = setTimeout(() => {
        const el = contentRef.current?.querySelector(`#${scrollToSection}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen, scrollToSection]);

  if (!isOpen || !research) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[80vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <svg className="w-5 h-5 mr-2 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Research Insights - Full Details
            </h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div ref={contentRef} className="flex-1 overflow-y-auto px-6 py-4">
            <ResearchFullView research={research} gapAnalysis={gapAnalysis} />
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Step status indicator
function StepStatus({
  label,
  isComplete,
  isActive
}: {
  label: string;
  isComplete: boolean;
  isActive: boolean;
}) {
  return (
    <div className="flex items-center space-x-2">
      {isComplete ? (
        <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      ) : isActive ? (
        <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-600 border-t-transparent" />
      ) : (
        <div className="w-5 h-5 rounded-full bg-gray-200" />
      )}
      <span className={`text-sm ${isComplete ? 'text-green-700' : isActive ? 'text-blue-700 font-medium' : 'text-gray-400'}`}>
        {label}
      </span>
    </div>
  );
}

export default function ResearchStep({
  currentStep,
  userProfile,
  jobPosting,
  profileMarkdown,
  jobMarkdown,
  research,
  gapAnalysis,
  progressMessages = [],
}: ResearchStepProps) {
  // Modal state
  const [researchModalOpen, setResearchModalOpen] = useState(false);
  const [researchModalSection, setResearchModalSection] = useState<string | null>(null);
  // New markdown editor modal state
  const [profileMarkdownModalOpen, setProfileMarkdownModalOpen] = useState(false);
  const [jobMarkdownModalOpen, setJobMarkdownModalOpen] = useState(false);

  const openResearchModal = (section?: string) => {
    setResearchModalSection(section || null);
    setResearchModalOpen(true);
  };

  // Determine step statuses based on what data is available
  // Check for actual content, not just truthy objects (empty {} is truthy but useless)
  const profileFetched = !!(userProfile?.name || profileMarkdown);
  const jobFetched = !!(jobPosting?.title || jobPosting?.company_name || jobMarkdown);
  const researchDone = !!research;
  const analysisDone = !!gapAnalysis;

  // Get the latest progress message for the current phase
  const latestMessage = progressMessages.length > 0
    ? progressMessages[progressMessages.length - 1]
    : null;

  const getMainMessage = () => {
    // If we have a recent progress message, use it
    if (latestMessage) {
      return latestMessage.message;
    }

    switch (currentStep) {
      case "ingest":
        if (!profileFetched && !jobFetched) {
          return "Fetching your profile and job details in parallel...";
        }
        if (profileFetched && !jobFetched) {
          return "Profile fetched! Waiting for job details...";
        }
        if (!profileFetched && jobFetched) {
          return "Job fetched! Waiting for profile details...";
        }
        return "Processing fetched data...";
      case "research":
        return "Researching company culture, tech stack, and similar employees...";
      case "analysis":
        return "Analyzing gaps and identifying what to highlight...";
      case "draft":
        return "Drafting your optimized resume...";
      default:
        return "Processing...";
    }
  };

  return (
    <div className="space-y-6">
      {/* Progress Steps */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between">
          <StepStatus
            label="Profile"
            isComplete={profileFetched}
            isActive={currentStep === "ingest" && !profileFetched}
          />
          <div className="flex-1 h-0.5 mx-2 bg-gray-200">
            <div className={`h-full transition-all duration-500 ${profileFetched ? 'bg-green-500 w-full' : 'bg-blue-500 w-0'}`} />
          </div>
          <StepStatus
            label="Job Details"
            isComplete={jobFetched}
            isActive={currentStep === "ingest" && !jobFetched}
          />
          <div className="flex-1 h-0.5 mx-2 bg-gray-200">
            <div className={`h-full transition-all duration-500 ${jobFetched ? 'bg-green-500 w-full' : 'bg-blue-500 w-0'}`} />
          </div>
          <StepStatus
            label="Research"
            isComplete={researchDone}
            isActive={currentStep === "research"}
          />
          <div className="flex-1 h-0.5 mx-2 bg-gray-200">
            <div className={`h-full transition-all duration-500 ${researchDone ? 'bg-green-500 w-full' : 'bg-blue-500 w-0'}`} />
          </div>
          <StepStatus
            label="Analysis"
            isComplete={analysisDone}
            isActive={currentStep === "analysis"}
          />
        </div>
      </div>

      {/* Status Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center space-x-3">
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-600 border-t-transparent flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-blue-800 font-medium block">{getMainMessage()}</span>
            {latestMessage?.detail && (
              <span className="text-blue-600 text-sm block mt-1 truncate">{latestMessage.detail}</span>
            )}
          </div>
        </div>
      </div>

      {/* Live Progress Feed - Show only last 3 updates */}
      {progressMessages.length > 0 && (currentStep === "ingest" || currentStep === "research") && (
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
          <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center">
            <svg className="w-4 h-4 mr-2 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Live Progress
          </h4>
          <div className="space-y-2">
            {progressMessages.slice(-3).map((msg, idx) => (
              <div
                key={idx}
                className={`text-sm ${idx === progressMessages.slice(-3).length - 1 ? 'text-blue-700 font-medium' : 'text-gray-600'}`}
              >
                <span className="inline-block w-2 h-2 rounded-full mr-2 flex-shrink-0"
                  style={{ backgroundColor: idx === progressMessages.slice(-3).length - 1 ? '#3b82f6' : '#9ca3af' }}
                />
                {msg.message}
                {msg.detail && (
                  <span className="text-gray-400 ml-1 text-xs">— {msg.detail}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profile Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <svg className="w-5 h-5 mr-2 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Your Profile
            </h3>
            {(userProfile || profileMarkdown) && (
              <div className="flex items-center gap-2">
                {profileMarkdown && (
                  <button
                    onClick={() => setProfileMarkdownModalOpen(true)}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
                  >
                    View/Edit Full Profile
                    <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                )}
              </div>
            )}
          </div>
          {userProfile ? (
            <div className="space-y-3">
              <div>
                <span className="font-medium">{userProfile.name}</span>
                {userProfile.headline && (
                  <p className="text-sm text-gray-600">{userProfile.headline}</p>
                )}
              </div>
              {/* Show structured experience if available */}
              {userProfile.experience && userProfile.experience.length > 0 ? (
                <div>
                  <p className="text-sm font-medium text-gray-700">
                    Experience ({userProfile.experience.length} roles)
                  </p>
                  <ul className="text-sm text-gray-600 space-y-1 border-l-2 border-gray-200 pl-3 mt-1">
                    {userProfile.experience.slice(0, 3).map((exp, idx) => (
                      <li key={idx}>
                        <span className="font-medium">{exp.position}</span> at {exp.company}
                        {exp.start_date && (
                          <span className="text-gray-400 text-xs ml-1">
                            ({exp.start_date} - {exp.end_date || "Present"})
                          </span>
                        )}
                      </li>
                    ))}
                    {userProfile.experience.length > 3 && (
                      <li className="text-gray-400 text-xs">
                        +{userProfile.experience.length - 3} more roles
                      </li>
                    )}
                  </ul>
                </div>
              ) : profileMarkdown ? (
                /* Show markdown preview when no structured experience */
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-1">Profile Content</p>
                  <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg max-h-32 overflow-hidden relative">
                    <div className="whitespace-pre-wrap">
                      {profileMarkdown.slice(0, 400)}
                      {profileMarkdown.length > 400 && "..."}
                    </div>
                    {profileMarkdown.length > 400 && (
                      <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-gray-50 to-transparent" />
                    )}
                  </div>
                  <button
                    onClick={() => setProfileMarkdownModalOpen(true)}
                    className="text-xs text-blue-600 hover:text-blue-800 mt-2 font-medium"
                  >
                    View full profile →
                  </button>
                </div>
              ) : null}
              {userProfile.skills && userProfile.skills.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700">
                    Skills ({userProfile.skills.length})
                  </p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {userProfile.skills.slice(0, 8).map((skill, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
                      >
                        {skill}
                      </span>
                    ))}
                    {userProfile.skills.length > 8 && (
                      <span className="px-2 py-0.5 text-gray-400 text-xs">
                        +{userProfile.skills.length - 8} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-gray-500 text-sm">Loading profile...</div>
          )}
        </div>

        {/* Job Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <svg className="w-5 h-5 mr-2 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              Target Job
            </h3>
            {(jobPosting || jobMarkdown) && (
              <div className="flex items-center gap-2">
                {jobMarkdown && (
                  <button
                    onClick={() => setJobMarkdownModalOpen(true)}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
                  >
                    View/Edit Job
                    <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                )}
              </div>
            )}
          </div>
          {jobPosting ? (
            <div className="space-y-3">
              <div>
                <span className="font-medium">{jobPosting.title}</span>
                {jobPosting.company_name && (
                  <p className="text-sm text-gray-600">
                    at {jobPosting.company_name}
                  </p>
                )}
                {jobPosting.location && (
                  <p className="text-sm text-gray-500">{jobPosting.location}</p>
                )}
              </div>
              {/* Show structured data if available */}
              {jobPosting.tech_stack && jobPosting.tech_stack.length > 0 ? (
                <div>
                  <p className="text-sm font-medium text-gray-700">Tech Stack</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {jobPosting.tech_stack.slice(0, 6).map((tech, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded"
                      >
                        {tech}
                      </span>
                    ))}
                    {jobPosting.tech_stack.length > 6 && (
                      <span className="px-2 py-0.5 text-gray-400 text-xs">
                        +{jobPosting.tech_stack.length - 6} more
                      </span>
                    )}
                  </div>
                </div>
              ) : null}
              {jobPosting.requirements && jobPosting.requirements.length > 0 ? (
                <div>
                  <p className="text-sm font-medium text-gray-700">
                    Key Requirements
                  </p>
                  <ul className="text-sm text-gray-600 list-disc list-inside">
                    {jobPosting.requirements.slice(0, 4).map((req, idx) => (
                      <li key={idx}>{req}</li>
                    ))}
                    {jobPosting.requirements.length > 4 && (
                      <li className="text-gray-400 text-xs list-none mt-1">
                        +{jobPosting.requirements.length - 4} more requirements
                      </li>
                    )}
                  </ul>
                </div>
              ) : jobMarkdown ? (
                /* Show markdown preview when no structured requirements */
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-1">Job Description</p>
                  <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg max-h-32 overflow-hidden relative">
                    <div className="whitespace-pre-wrap">
                      {jobMarkdown.slice(0, 400)}
                      {jobMarkdown.length > 400 && "..."}
                    </div>
                    {jobMarkdown.length > 400 && (
                      <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-gray-50 to-transparent" />
                    )}
                  </div>
                  <button
                    onClick={() => setJobMarkdownModalOpen(true)}
                    className="text-xs text-blue-600 hover:text-blue-800 mt-2 font-medium"
                  >
                    View full job posting →
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="text-gray-500 text-sm">Loading job details...</div>
          )}
        </div>
      </div>

      {/* Markdown Display Modals */}
      <ProfileEditorModal
        isOpen={profileMarkdownModalOpen}
        onClose={() => setProfileMarkdownModalOpen(false)}
        title="Your LinkedIn Profile"
        markdown={profileMarkdown}
        onSave={() => {
          setProfileMarkdownModalOpen(false);
        }}
      />
      <ProfileEditorModal
        isOpen={jobMarkdownModalOpen}
        onClose={() => setJobMarkdownModalOpen(false)}
        title="Job Posting"
        markdown={jobMarkdown}
        onSave={() => {
          setJobMarkdownModalOpen(false);
        }}
      />

      {/* Research Findings */}
      {research && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <svg className="w-5 h-5 mr-2 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Research Insights
            </h3>
            <button
              onClick={() => openResearchModal()}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
            >
              Show More
              <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </button>
          </div>
          <div className="space-y-4">
            {/* Row 0: Company Overview - if available */}
            {research.company_overview && (
              <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
                <p className="text-sm font-medium text-blue-800 mb-1">Company Overview</p>
                <p className="text-sm text-blue-700">
                  {research.company_overview}
                </p>
              </div>
            )}

            {/* Row 1: Culture + Values */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium text-gray-700">
                  Company Culture
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  {research.company_culture || ''}
                </p>
              </div>
              {research.company_values && research.company_values.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700">Company Values</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {research.company_values.map((value, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded"
                      >
                        {value}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Row 2: Tech Stack Preview - show all with usage */}
            {research.tech_stack_details && research.tech_stack_details.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Tech Stack</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {research.tech_stack_details.slice(0, 8).map((tech, idx) => {
                    const style = importanceStyle(tech.importance);
                    return (
                    <div
                      key={idx}
                      className={`px-3 py-2 text-xs rounded-lg ${style.border}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className={`font-medium ${style.bg.split(' ')[1] || 'text-gray-700'}`}>{tech.technology}</span>
                        {tech.importance && (
                          <span className={`px-1.5 py-0.5 text-[10px] rounded ${style.badge}`}>{tech.importance}</span>
                        )}
                      </div>
                      {tech.usage && (
                        <p className="text-gray-500 mt-1 line-clamp-2">{tech.usage}</p>
                      )}
                    </div>
                    );
                  })}
                </div>
                {research.tech_stack_details.length > 8 && (
                  <button
                    onClick={() => openResearchModal("section-tech-stack")}
                    className="mt-2 text-xs text-blue-600 hover:text-blue-800"
                  >
                    +{research.tech_stack_details.length - 8} more technologies
                  </button>
                )}
              </div>
            )}

            {/* Row 3: Similar Profiles - enhanced with current company and skills */}
            {research.similar_profiles && research.similar_profiles.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Similar Successful Profiles</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {research.similar_profiles.slice(0, 4).map((profile, idx) => (
                    <div key={idx} className="text-sm border-l-3 border-blue-300 pl-3 bg-blue-50/50 py-2 pr-2 rounded-r">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-gray-800 truncate">{profile.name}</p>
                          <p className="text-gray-600 text-xs truncate">{profile.headline}</p>
                          {profile.current_company && (
                            <p className="text-gray-500 text-xs mt-0.5">@ {profile.current_company}</p>
                          )}
                        </div>
                        {profile.url && (
                          <a
                            href={profile.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 ml-2 flex-shrink-0"
                            title="View Profile"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </a>
                        )}
                      </div>
                      {profile.key_skills && profile.key_skills.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {profile.key_skills.slice(0, 4).map((skill, i) => (
                            <span key={i} className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[10px] rounded">
                              {skill}
                            </span>
                          ))}
                          {profile.key_skills.length > 4 && (
                            <span className="text-[10px] text-gray-400">+{profile.key_skills.length - 4}</span>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {research.similar_profiles.length > 4 && (
                  <button
                    onClick={() => openResearchModal("section-similar-profiles")}
                    className="mt-2 text-xs text-blue-600 hover:text-blue-800"
                  >
                    +{research.similar_profiles.length - 4} more profiles
                  </button>
                )}
              </div>
            )}

            {/* Row 4: Industry Trends */}
            {research.industry_trends && research.industry_trends.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Industry Trends</p>
                <ul className="text-xs text-gray-600 space-y-1.5 bg-green-50/50 p-3 rounded-lg">
                  {research.industry_trends.slice(0, 5).map((trend, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="text-green-500 mr-2 mt-0.5">→</span>
                      <span>{trend}</span>
                    </li>
                  ))}
                  {research.industry_trends.length > 5 && (
                    <li>
                      <button
                        onClick={() => openResearchModal("section-industry-trends")}
                        className="text-blue-600 hover:text-blue-800 ml-4"
                      >
                        +{research.industry_trends.length - 5} more trends
                      </button>
                    </li>
                  )}
                </ul>
              </div>
            )}

            {/* Row 5: Hiring Patterns + Company News */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {research.hiring_patterns && (
                <div className="bg-amber-50/50 p-3 rounded-lg border border-amber-100">
                  <p className="text-sm font-medium text-amber-800 mb-1 flex items-center">
                    <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Hiring Patterns
                  </p>
                  <p className="text-xs text-amber-700">
                    {research.hiring_patterns}
                  </p>
                </div>
              )}
              {research.company_news && research.company_news.length > 0 && (
                <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                  <p className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                    <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                    </svg>
                    Recent News
                  </p>
                  <ul className="text-xs text-gray-600 space-y-1.5">
                    {research.company_news.slice(0, 4).map((news, idx) => (
                      <li key={idx} className="flex items-start">
                        <span className="text-gray-400 mr-1.5">•</span>
                        <span className="line-clamp-2">{news}</span>
                      </li>
                    ))}
                    {research.company_news.length > 4 && (
                      <li>
                        <button
                          onClick={() => openResearchModal("section-company-news")}
                          className="text-blue-600 hover:text-blue-800 ml-3"
                        >
                          +{research.company_news.length - 4} more news items
                        </button>
                      </li>
                    )}
                  </ul>
                </div>
              )}
            </div>

            {/* Row 6: Hiring Criteria + Ideal Profile */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Hiring Criteria Preview */}
              {research.hiring_criteria && (
                <div className="bg-amber-50/50 p-3 rounded-lg border border-amber-200">
                  <p className="text-sm font-medium text-amber-800 mb-2 flex items-center">
                    <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Hiring Criteria
                  </p>
                  {research.hiring_criteria.must_haves && research.hiring_criteria.must_haves.length > 0 && (
                    <div className="mb-2">
                      <p className="text-xs font-medium text-red-700">Must-Haves:</p>
                      <ul className="text-xs text-gray-600 space-y-0.5">
                        {research.hiring_criteria.must_haves.slice(0, 3).map((item, idx) => (
                          <li key={idx} className="flex items-start">
                            <span className="text-red-400 mr-1">•</span>
                            <span className="line-clamp-1">{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {((research.hiring_criteria.keywords && research.hiring_criteria.keywords.length > 0) ||
                    (research.hiring_criteria.ats_keywords && research.hiring_criteria.ats_keywords.length > 0)) && (
                    <div className="flex flex-wrap gap-1">
                      {[...(research.hiring_criteria.keywords || []), ...(research.hiring_criteria.ats_keywords || [])].slice(0, 6).map((kw, idx) => (
                        <span key={idx} className="px-1.5 py-0.5 bg-amber-100 text-amber-700 text-[10px] rounded">
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => openResearchModal("section-hiring-criteria")}
                    className="text-xs text-blue-600 hover:text-blue-800 mt-2"
                  >
                    View full criteria →
                  </button>
                </div>
              )}

              {/* Ideal Profile Preview */}
              {research.ideal_profile && (
                <div className="bg-green-50/50 p-3 rounded-lg border border-green-200">
                  <p className="text-sm font-medium text-green-800 mb-2 flex items-center">
                    <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Ideal Profile
                  </p>
                  {research.ideal_profile.headline && (
                    <div className="mb-2">
                      <p className="text-xs font-medium text-green-700">Recommended Headline:</p>
                      <p className="text-xs text-gray-700 bg-white rounded px-2 py-1 mt-0.5 border border-green-100 line-clamp-2">
                        {research.ideal_profile.headline}
                      </p>
                    </div>
                  )}
                  {research.ideal_profile.skills_priority && research.ideal_profile.skills_priority.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {research.ideal_profile.skills_priority.slice(0, 5).map((skill, idx) => (
                        <span key={idx} className="px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] rounded">
                          {skill}
                        </span>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => openResearchModal("section-ideal-profile")}
                    className="text-xs text-blue-600 hover:text-blue-800 mt-2"
                  >
                    View full profile →
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Research Modal */}
      <ResearchModal
        isOpen={researchModalOpen}
        onClose={() => { setResearchModalOpen(false); setResearchModalSection(null); }}
        research={research}
        gapAnalysis={gapAnalysis}
        scrollToSection={researchModalSection}
      />

      {/* Gap Analysis */}
      {gapAnalysis && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Gap Analysis
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-green-700">Strengths</p>
              <ul className="text-sm text-gray-600 list-disc list-inside mt-1">
                {gapAnalysis.strengths.slice(0, 4).map((s, idx) => (
                  <li key={idx}>{s}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-sm font-medium text-amber-700">
                Areas to Address
              </p>
              <ul className="text-sm text-gray-600 list-disc list-inside mt-1">
                {gapAnalysis.gaps.slice(0, 4).map((g, idx) => (
                  <li key={idx}>{g}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
