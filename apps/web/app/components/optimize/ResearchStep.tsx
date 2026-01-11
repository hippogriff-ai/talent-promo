"use client";

import { useState } from "react";
import {
  UserProfile,
  JobPosting,
  ResearchFindings,
  GapAnalysis,
  WorkflowStep,
} from "../../hooks/useWorkflow";

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
  research: ResearchFindings | null;
  gapAnalysis: GapAnalysis | null;
  progressMessages?: ProgressMessage[];
  onUpdateProfile?: (profile: UserProfile) => void;
  onUpdateJob?: (job: JobPosting) => void;
}

// Modal component for viewing/editing profile or job
function DataModal({
  isOpen,
  onClose,
  title,
  data,
  type,
  onSave,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  data: UserProfile | JobPosting | null;
  type: "profile" | "job";
  onSave?: (data: UserProfile | JobPosting) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedJson, setEditedJson] = useState("");
  const [error, setError] = useState("");

  if (!isOpen || !data) return null;

  const handleEdit = () => {
    setEditedJson(JSON.stringify(data, null, 2));
    setIsEditing(true);
    setError("");
  };

  const handleSave = () => {
    try {
      const parsed = JSON.parse(editedJson);
      onSave?.(parsed);
      setIsEditing(false);
      setError("");
    } catch {
      setError("Invalid JSON format");
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setError("");
  };

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
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
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
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {isEditing ? (
              <div className="space-y-3">
                <p className="text-sm text-gray-600">
                  Edit the JSON below to correct any parsing errors:
                </p>
                <textarea
                  value={editedJson}
                  onChange={(e) => setEditedJson(e.target.value)}
                  className="w-full h-96 font-mono text-sm p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  spellCheck={false}
                />
                {error && (
                  <p className="text-red-600 text-sm">{error}</p>
                )}
              </div>
            ) : type === "profile" ? (
              <ProfileFullView profile={data as UserProfile} />
            ) : (
              <JobFullView job={data as JobPosting} />
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
            {isEditing ? (
              <>
                <button
                  onClick={handleCancel}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                >
                  Save Changes
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleEdit}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Edit JSON
                </button>
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                >
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Full profile view for modal
function ProfileFullView({ profile }: { profile: UserProfile }) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h4 className="text-xl font-bold text-gray-900">{profile.name}</h4>
        {profile.headline && (
          <p className="text-gray-600 mt-1">{profile.headline}</p>
        )}
        {profile.email && (
          <p className="text-sm text-gray-500 mt-1">{profile.email}</p>
        )}
        {profile.location && (
          <p className="text-sm text-gray-500">{profile.location}</p>
        )}
      </div>

      {/* Summary */}
      {profile.summary && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Summary</h5>
          <p className="text-gray-600 text-sm whitespace-pre-wrap">{profile.summary}</p>
        </div>
      )}

      {/* Experience */}
      {profile.experience && profile.experience.length > 0 && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Experience ({profile.experience.length})</h5>
          <div className="space-y-3">
            {profile.experience.map((exp, idx) => (
              <div key={idx} className="border-l-2 border-blue-200 pl-3">
                <p className="font-medium text-gray-900">{exp.position}</p>
                <p className="text-sm text-gray-600">{exp.company}</p>
                <p className="text-xs text-gray-500">
                  {exp.start_date} - {exp.end_date || "Present"}
                </p>
                {exp.achievements && exp.achievements.length > 0 && (
                  <ul className="mt-2 text-sm text-gray-600 list-disc list-inside">
                    {exp.achievements.map((ach, i) => (
                      <li key={i}>{ach}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Education */}
      {profile.education && profile.education.length > 0 && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Education</h5>
          <div className="space-y-2">
            {profile.education.map((edu, idx) => (
              <div key={idx}>
                <p className="font-medium text-gray-900">{edu.institution}</p>
                <p className="text-sm text-gray-600">
                  {edu.degree} {edu.field_of_study && `in ${edu.field_of_study}`}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skills */}
      {profile.skills && profile.skills.length > 0 && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Skills ({profile.skills.length})</h5>
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((skill, idx) => (
              <span
                key={idx}
                className="px-2 py-1 bg-gray-100 text-gray-700 text-sm rounded"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Full job view for modal
function JobFullView({ job }: { job: JobPosting }) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h4 className="text-xl font-bold text-gray-900">{job.title}</h4>
        <p className="text-gray-600 mt-1">at {job.company_name}</p>
        {job.location && (
          <p className="text-sm text-gray-500">{job.location}</p>
        )}
        {job.work_type && (
          <span className="inline-block mt-2 px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
            {job.work_type}
          </span>
        )}
      </div>

      {/* Description */}
      {job.description && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Description</h5>
          <p className="text-gray-600 text-sm whitespace-pre-wrap">{job.description}</p>
        </div>
      )}

      {/* Requirements */}
      {job.requirements && job.requirements.length > 0 && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Requirements</h5>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            {job.requirements.map((req, idx) => (
              <li key={idx}>{req}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Responsibilities */}
      {job.responsibilities && job.responsibilities.length > 0 && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Responsibilities</h5>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            {job.responsibilities.map((resp, idx) => (
              <li key={idx}>{resp}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Tech Stack */}
      {job.tech_stack && job.tech_stack.length > 0 && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Tech Stack</h5>
          <div className="flex flex-wrap gap-2">
            {job.tech_stack.map((tech, idx) => (
              <span
                key={idx}
                className="px-2 py-1 bg-blue-100 text-blue-700 text-sm rounded"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Benefits */}
      {job.benefits && job.benefits.length > 0 && (
        <div>
          <h5 className="font-semibold text-gray-800 mb-2">Benefits</h5>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            {job.benefits.map((ben, idx) => (
              <li key={idx}>{ben}</li>
            ))}
          </ul>
        </div>
      )}
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
  research,
  gapAnalysis,
  progressMessages = [],
  onUpdateProfile,
  onUpdateJob,
}: ResearchStepProps) {
  // Modal state
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [jobModalOpen, setJobModalOpen] = useState(false);

  // Determine step statuses based on what data is available
  const profileFetched = !!userProfile;
  const jobFetched = !!jobPosting;
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
            {userProfile && (
              <button
                onClick={() => setProfileModalOpen(true)}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
              >
                Show More
                <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </button>
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
              {userProfile.experience && userProfile.experience.length > 0 && (
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
              )}
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
            {jobPosting && (
              <button
                onClick={() => setJobModalOpen(true)}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
              >
                Show More
                <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </button>
            )}
          </div>
          {jobPosting ? (
            <div className="space-y-3">
              <div>
                <span className="font-medium">{jobPosting.title}</span>
                <p className="text-sm text-gray-600">
                  at {jobPosting.company_name}
                </p>
                {jobPosting.location && (
                  <p className="text-sm text-gray-500">{jobPosting.location}</p>
                )}
              </div>
              {jobPosting.tech_stack && jobPosting.tech_stack.length > 0 && (
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
              )}
              {jobPosting.requirements && jobPosting.requirements.length > 0 && (
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
              )}
            </div>
          ) : (
            <div className="text-gray-500 text-sm">Loading job details...</div>
          )}
        </div>
      </div>

      {/* Modals */}
      <DataModal
        isOpen={profileModalOpen}
        onClose={() => setProfileModalOpen(false)}
        title="Your Profile - Full Details"
        data={userProfile}
        type="profile"
        onSave={onUpdateProfile ? (data) => onUpdateProfile(data as UserProfile) : undefined}
      />
      <DataModal
        isOpen={jobModalOpen}
        onClose={() => setJobModalOpen(false)}
        title="Target Job - Full Details"
        data={jobPosting}
        type="job"
        onSave={onUpdateJob ? (data) => onUpdateJob(data as JobPosting) : undefined}
      />

      {/* Research Findings */}
      {research && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Research Insights
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-gray-700">
                Company Culture
              </p>
              <p className="text-sm text-gray-600 mt-1">
                {research.company_culture.slice(0, 200)}...
              </p>
            </div>
            {research.company_values.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700">Values</p>
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
        </div>
      )}

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
