"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Header from "./components/layout/Header";
import OnboardingGuide from "./components/layout/OnboardingGuide";
import { useTurnstile } from "./hooks/useTurnstile";

const FIRST_VISIT_KEY = "talent_promo:first_visit";
const PENDING_INPUT_KEY = "talent_promo:pending_input";
const RECENT_LINKEDIN_KEY = "talent_promo:recent_linkedin";
const RECENT_JOB_KEY = "talent_promo:recent_job";
const MAX_RECENT = 2;

const features = [
  {
    title: "Research",
    description: "AI analyzes your profile and target job to identify key requirements and gaps.",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
    color: "from-blue-500 to-cyan-500",
  },
  {
    title: "Discovery",
    description: "Guided conversation uncovers hidden experiences that match job requirements.",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
    color: "from-green-500 to-emerald-500",
  },
  {
    title: "Drafting",
    description: "Generate an ATS-optimized resume with smart suggestions and rich editing.",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    ),
    color: "from-orange-500 to-yellow-500",
  },
  {
    title: "Export",
    description: "Download in multiple formats with ATS analysis and LinkedIn optimization tips.",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
    ),
    color: "from-green-500 to-emerald-500",
  },
];

const benefits = [
  {
    title: "ATS-Optimized",
    description: "Beat applicant tracking systems with keyword-optimized formatting",
    icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  {
    title: "Tailored Content",
    description: "Every resume is customized for your specific target job",
    icon: "M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z",
  },
  {
    title: "Multiple Formats",
    description: "Download as PDF, Word, or plain text instantly",
    icon: "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z",
  },
];

export default function Home() {
  const router = useRouter();
  const [showGuide, setShowGuide] = useState(false);
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const [inputMode, setInputMode] = useState<"linkedin" | "paste" | "upload">("paste");
  const [jobInputMode, setJobInputMode] = useState<"url" | "paste">("url");
  const [resumeText, setResumeText] = useState("");
  const [jobText, setJobText] = useState("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState("");
  const [showResumePreview, setShowResumePreview] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [honeypot, setHoneypot] = useState("");  // Bot trap - should remain empty
  const turnstile = useTurnstile();

  // Recent URLs for quick selection
  const [recentLinkedin, setRecentLinkedin] = useState<string[]>([]);
  const [recentJob, setRecentJob] = useState<string[]>([]);
  const [showLinkedinDropdown, setShowLinkedinDropdown] = useState(false);
  const [showJobDropdown, setShowJobDropdown] = useState(false);
  const linkedinInputRef = useRef<HTMLInputElement>(null);
  const jobInputRef = useRef<HTMLInputElement>(null);

  // Handle mode query param (e.g., /?mode=paste from error recovery)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const mode = params.get("mode");
    if (mode === "paste") {
      setInputMode("paste");
      // Clear the query param from URL without reload
      window.history.replaceState({}, "", "/");
    }
  }, []);

  useEffect(() => {
    // Check if first visit
    const hasVisited = localStorage.getItem(FIRST_VISIT_KEY);
    if (!hasVisited) {
      setShowGuide(true);
      localStorage.setItem(FIRST_VISIT_KEY, "true");
    }

    // Load recent URLs
    try {
      const storedLinkedin = localStorage.getItem(RECENT_LINKEDIN_KEY);
      const storedJob = localStorage.getItem(RECENT_JOB_KEY);
      if (storedLinkedin) setRecentLinkedin(JSON.parse(storedLinkedin));
      if (storedJob) setRecentJob(JSON.parse(storedJob));
    } catch (e) {
      console.error("Failed to load recent URLs:", e);
    }
  }, []);

  // Save URL to recent list (keep last 2, no duplicates)
  const saveRecentUrl = (key: string, url: string, current: string[]) => {
    if (!url) return current;
    const filtered = current.filter(u => u !== url);
    const updated = [url, ...filtered].slice(0, MAX_RECENT);
    localStorage.setItem(key, JSON.stringify(updated));
    return updated;
  };

  const isValidUrl = (url: string) => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploadError("");
    setUploadSuccess("");
    setUploadedFile(file);

    // Validate file type
    const name = file.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
      setUploadError("Only PDF and DOCX files are supported.");
      setUploadedFile(null);
      return;
    }

    // Validate file size (5MB)
    if (file.size > 5 * 1024 * 1024) {
      setUploadError("File size exceeds 5MB limit.");
      setUploadedFile(null);
      return;
    }

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/documents/parse", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const contentType = res.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        throw new Error("Server returned an unexpected response. Please try again.");
      }

      const data = await res.json();
      if (!data.success) {
        setUploadError(data.error || "Failed to parse document.");
        setUploadedFile(null);
        return;
      }

      if (!data.text || data.text.trim().length < 20) {
        setUploadError("Could not extract meaningful text from the file. Try pasting your resume instead.");
        setUploadedFile(null);
        return;
      }

      // Success - populate resume text and switch to paste mode to show it
      setResumeText(data.text);
      setInputMode("paste");
      setUploadedFile(null);
      setUploadSuccess(`Extracted text from ${file.name}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      const isNetworkError = message === "Failed to fetch" || message.includes("NetworkError");
      setUploadError(
        isNetworkError
          ? "Could not reach the server. Please check your connection and try again."
          : message || "Failed to upload file. Please try again."
      );
      setUploadedFile(null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const canSubmit = () => {
    const hasProfile = inputMode === "linkedin"
      ? linkedinUrl && isValidUrl(linkedinUrl)
      : inputMode === "upload"
        ? false  // Upload auto-switches to paste mode on success
        : resumeText.trim().length > 50;
    const hasJob = jobInputMode === "url"
      ? jobUrl && isValidUrl(jobUrl)
      : jobText.trim().length > 50;
    return hasProfile && hasJob && turnstile.isReady && !isSubmitting;
  };

  const handleSubmit = async () => {
    setError("");

    // Honeypot check - bots will fill this hidden field
    if (honeypot) {
      // Silently fail for bots - looks like success but does nothing
      setIsSubmitting(true);
      setTimeout(() => setIsSubmitting(false), 2000);
      return;
    }

    if (!canSubmit()) {
      setError("Please fill in all required fields with valid URLs");
      return;
    }

    setIsSubmitting(true);

    // Save URLs to recent list
    if (inputMode === "linkedin" && linkedinUrl) {
      setRecentLinkedin(saveRecentUrl(RECENT_LINKEDIN_KEY, linkedinUrl, recentLinkedin));
    }
    if (jobInputMode === "url" && jobUrl) {
      setRecentJob(saveRecentUrl(RECENT_JOB_KEY, jobUrl, recentJob));
    }

    // Store the input data for the optimize page to pick up
    const inputData = {
      linkedinUrl: inputMode === "linkedin" ? linkedinUrl : undefined,
      jobUrl: jobInputMode === "url" ? jobUrl : undefined,
      resumeText: inputMode === "paste" ? resumeText : undefined,
      jobText: jobInputMode === "paste" ? jobText : undefined,
      turnstileToken: turnstile.token || undefined,
    };

    localStorage.setItem(PENDING_INPUT_KEY, JSON.stringify(inputData));

    // Navigate to optimize page
    router.push("/optimize");
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <Header showGuide={() => setShowGuide(true)} />

      <OnboardingGuide isOpen={showGuide} onClose={() => setShowGuide(false)} />

      {/* Resume text preview modal */}
      {showResumePreview && resumeText && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowResumePreview(false)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-semibold text-gray-900">Extracted Resume Text</h3>
              <button onClick={() => setShowResumePreview(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-6 py-4 overflow-y-auto flex-1">
              <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">{resumeText}</pre>
            </div>
            <div className="px-6 py-3 border-t bg-gray-50 rounded-b-xl flex justify-end">
              <button onClick={() => setShowResumePreview(false)} className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Demo Disclaimer Banner */}
      <div className="bg-amber-50 border-b border-amber-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="text-sm text-amber-900">
              <p className="font-semibold mb-1">
                Demo App &mdash; Built by Vicki | Not for commercial use
              </p>
              <ul className="space-y-0.5 text-amber-800">
                <li><strong>No server-side storage.</strong> All data stays in your browser and is never saved on our servers.</li>
                <li><strong>Tracing enabled.</strong> We use LangSmith for observability. Avoid entering sensitive PII (SSN, financial info, etc.).</li>
                <li><strong>Daily usage limit.</strong> Token costs are on me, so there&apos;s a cap per day.</li>
              </ul>
              <p className="mt-1.5 text-amber-700">
                Want unlimited runs? Clone the{" "}
                <a
                  href="https://github.com/hippogriff-ai/talent-promo"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium underline hover:text-amber-900"
                >
                  GitHub repo
                </a>{" "}
                and use your own API key.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Hero Section with Input Form */}
      <section className="relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-0 -left-4 w-72 h-72 bg-green-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob" />
          <div className="absolute top-0 -right-4 w-72 h-72 bg-yellow-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob animation-delay-2000" />
          <div className="absolute -bottom-8 left-20 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob animation-delay-4000" />
        </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
          <div className="grid lg:grid-cols-2 gap-12 items-start">
            {/* Left side - Headlines */}
            <div>
              {/* Badge */}
              <div className="inline-flex items-center px-4 py-1.5 rounded-full bg-green-100 text-green-700 text-sm font-medium mb-6">
                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                AI-Powered Resume Optimization
              </div>

              {/* Headline */}
              <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 tracking-tight mb-6">
                Land Your Dream Job with
                <span className="block text-transparent bg-clip-text bg-gradient-to-r from-green-600 to-emerald-600">
                  AI-Tailored Resumes
                </span>
              </h1>

              {/* Subheadline */}
              <p className="text-lg text-gray-600 mb-8">
                Transform your LinkedIn profile into an ATS-optimized resume perfectly tailored
                for any job posting. Our AI uncovers your hidden strengths.
              </p>

              {/* Trust indicators */}
              <div className="flex flex-wrap gap-6 text-sm text-gray-500">
                <div className="flex items-center">
                  <svg className="w-5 h-5 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Free demo
                </div>
                <div className="flex items-center">
                  <svg className="w-5 h-5 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  No password needed
                </div>
                <div className="flex items-center">
                  <svg className="w-5 h-5 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  2-5 min process
                </div>
              </div>
            </div>

            {/* Right side - Input Form */}
            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 sm:p-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Start Your Optimization
              </h2>
              <p className="text-gray-600 text-sm mb-6">
                Enter your profile and target job to get started.
              </p>

              {/* Error message */}
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {error}
                </div>
              )}

              {/* Honeypot field - hidden from humans, visible to bots */}
              <div className="absolute -left-[9999px]" aria-hidden="true">
                <input
                  type="text"
                  name="website"
                  tabIndex={-1}
                  autoComplete="off"
                  value={honeypot}
                  onChange={(e) => setHoneypot(e.target.value)}
                />
              </div>

              {/* Profile Input */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Your Profile
                </label>

                {/* Toggle */}
                <div className="flex mb-3 bg-gray-100 rounded-lg p-1">
                  <button
                    onClick={() => setInputMode("paste")}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all ${
                      inputMode === "paste"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <span className="flex items-center justify-center">
                      <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Paste
                    </span>
                  </button>
                  <button
                    onClick={() => setInputMode("upload")}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all ${
                      inputMode === "upload"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <span className="flex items-center justify-center">
                      <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                      </svg>
                      Upload
                    </span>
                  </button>
                  <button
                    onClick={() => setInputMode("linkedin")}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all ${
                      inputMode === "linkedin"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <span className="flex items-center justify-center">
                      <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                      </svg>
                      LinkedIn
                    </span>
                  </button>
                </div>

                {inputMode === "paste" ? (
                  <div>
                    {uploadSuccess && (
                      <div className="mb-2 flex items-center justify-between">
                        <p className="text-xs text-green-700 flex items-center">
                          <svg className="w-3.5 h-3.5 mr-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                          {uploadSuccess}
                        </p>
                        <button
                          type="button"
                          onClick={() => setShowResumePreview(true)}
                          className="text-xs text-green-700 hover:text-green-900 font-medium underline"
                        >
                          Preview full text
                        </button>
                      </div>
                    )}
                    <textarea
                      placeholder="Paste your resume text here..."
                      value={resumeText}
                      onChange={(e) => { setResumeText(e.target.value); setUploadSuccess(""); }}
                      rows={4}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 transition-all resize-none"
                    />
                  </div>
                ) : inputMode === "upload" ? (
                  <div>
                    <div
                      onDrop={handleDrop}
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                      onClick={() => fileInputRef.current?.click()}
                      className={`relative flex flex-col items-center justify-center px-4 py-8 border-2 border-dashed rounded-xl cursor-pointer transition-all ${
                        isDragOver
                          ? "border-green-500 bg-green-50"
                          : isUploading
                            ? "border-gray-300 bg-gray-50 cursor-wait"
                            : "border-gray-300 hover:border-green-400 hover:bg-gray-50"
                      }`}
                    >
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.docx"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) handleFileUpload(file);
                          e.target.value = "";  // Reset so same file can be re-selected
                        }}
                      />
                      {isUploading ? (
                        <>
                          <svg className="animate-spin w-8 h-8 text-green-500 mb-2" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          <p className="text-sm text-gray-600">Extracting text from {uploadedFile?.name}...</p>
                        </>
                      ) : (
                        <>
                          <svg className="w-8 h-8 text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                          </svg>
                          <p className="text-sm font-medium text-gray-700">
                            Drop your resume here or click to browse
                          </p>
                          <p className="text-xs text-gray-500 mt-1">PDF or DOCX, max 5MB</p>
                        </>
                      )}
                    </div>
                    {uploadError && (
                      <p className="mt-2 text-xs text-red-600 flex items-center">
                        <svg className="w-3.5 h-3.5 mr-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                        {uploadError}
                      </p>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className="relative">
                      <input
                        ref={linkedinInputRef}
                        type="url"
                        placeholder="https://linkedin.com/in/yourprofile"
                        value={linkedinUrl}
                        onChange={(e) => setLinkedinUrl(e.target.value)}
                        onFocus={() => setShowLinkedinDropdown(recentLinkedin.length > 0)}
                        onBlur={() => setTimeout(() => setShowLinkedinDropdown(false), 150)}
                        className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 transition-all"
                      />
                      {showLinkedinDropdown && recentLinkedin.length > 0 && (
                        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
                          <div className="px-3 py-1.5 text-xs font-medium text-gray-500 bg-gray-50 border-b">
                            Recent
                          </div>
                          {recentLinkedin.map((url, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => {
                                setLinkedinUrl(url);
                                setShowLinkedinDropdown(false);
                              }}
                              className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-green-50 hover:text-green-700 truncate"
                            >
                              {url}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <p className="mt-2 text-xs text-amber-600 flex items-center">
                      <svg className="w-3.5 h-3.5 mr-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      LinkedIn blocks direct fetching. We&apos;ll search the web to find your profile.
                    </p>
                  </div>
                )}
              </div>

              {/* Job Input */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Target Job Posting
                </label>

                {/* Toggle */}
                <div className="flex mb-3 bg-gray-100 rounded-lg p-1">
                  <button
                    onClick={() => setJobInputMode("url")}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all ${
                      jobInputMode === "url"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <span className="flex items-center justify-center">
                      <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                      </svg>
                      Job URL
                    </span>
                  </button>
                  <button
                    onClick={() => setJobInputMode("paste")}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all ${
                      jobInputMode === "paste"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <span className="flex items-center justify-center">
                      <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Paste Job Description
                    </span>
                  </button>
                </div>

                {jobInputMode === "url" ? (
                  <div className="relative">
                    <input
                      ref={jobInputRef}
                      type="url"
                      placeholder="https://jobs.example.com/software-engineer"
                      value={jobUrl}
                      onChange={(e) => setJobUrl(e.target.value)}
                      onFocus={() => setShowJobDropdown(recentJob.length > 0)}
                      onBlur={() => setTimeout(() => setShowJobDropdown(false), 150)}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 transition-all"
                    />
                    {showJobDropdown && recentJob.length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
                        <div className="px-3 py-1.5 text-xs font-medium text-gray-500 bg-gray-50 border-b">
                          Recent
                        </div>
                        {recentJob.map((url, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              setJobUrl(url);
                              setShowJobDropdown(false);
                            }}
                            className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-green-50 hover:text-green-700 truncate"
                          >
                            {url}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <textarea
                    placeholder="Paste the full job description here..."
                    value={jobText}
                    onChange={(e) => setJobText(e.target.value)}
                    rows={4}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 transition-all resize-none"
                  />
                )}
              </div>

              {/* Turnstile bot protection (invisible widget) */}
              <div ref={turnstile.containerRef} className="mb-4" />
              {turnstile.hasError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  Bot protection check failed. Please refresh the page and try again.
                </div>
              )}

              {/* Submit Button */}
              <button
                onClick={handleSubmit}
                disabled={!canSubmit()}
                className="w-full py-4 bg-green-600 text-white rounded-xl font-semibold hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all shadow-lg shadow-green-500/30 hover:shadow-xl hover:shadow-green-500/40 disabled:shadow-none flex items-center justify-center"
              >
                {isSubmitting ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Starting...
                  </>
                ) : (
                  <>
                    Start Optimization
                    <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                  </>
                )}
              </button>

              <p className="mt-4 text-center text-xs text-gray-500">
                Takes 2-5 minutes. You&apos;ll review before exporting.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
              Four Steps to Your Perfect Resume
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Our AI-powered workflow guides you through creating a resume that stands out
              to both humans and applicant tracking systems.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div
                key={feature.title}
                className="relative group"
              >
                {/* Connector line */}
                {index < features.length - 1 && (
                  <div className="hidden lg:block absolute top-12 left-full w-full h-0.5 bg-gray-200 -z-10" />
                )}

                <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover:shadow-lg transition-all hover:-translate-y-1">
                  {/* Step number */}
                  <div className="absolute -top-3 -left-3 w-8 h-8 bg-white border-2 border-gray-200 rounded-full flex items-center justify-center text-sm font-bold text-gray-500">
                    {index + 1}
                  </div>

                  {/* Icon */}
                  <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${feature.color} text-white flex items-center justify-center mb-4`}>
                    {feature.icon}
                  </div>

                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-gray-600">
                    {feature.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-6">
                Why Choose Talent Promo?
              </h2>
              <p className="text-lg text-gray-600 mb-8">
                Stop sending generic resumes that get lost in the pile. Our AI ensures
                your resume speaks directly to each job&apos;s requirements.
              </p>

              <div className="space-y-6">
                {benefits.map((benefit) => (
                  <div key={benefit.title} className="flex items-start">
                    <div className="flex-shrink-0 w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center text-green-600">
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={benefit.icon} />
                      </svg>
                    </div>
                    <div className="ml-4">
                      <h3 className="text-lg font-semibold text-gray-900">{benefit.title}</h3>
                      <p className="text-gray-600">{benefit.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Preview mockup */}
            <div className="relative">
              <div className="bg-white rounded-2xl shadow-2xl p-6 border border-gray-100">
                <div className="flex items-center space-x-2 mb-4">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-yellow-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                </div>
                <div className="space-y-4">
                  <div className="h-8 bg-gray-100 rounded w-3/4" />
                  <div className="h-4 bg-gray-100 rounded w-full" />
                  <div className="h-4 bg-gray-100 rounded w-5/6" />
                  <div className="mt-6 pt-4 border-t border-gray-100">
                    <div className="h-6 bg-green-100 rounded w-1/3 mb-3" />
                    <div className="h-3 bg-gray-100 rounded w-full mb-2" />
                    <div className="h-3 bg-gray-100 rounded w-4/5 mb-2" />
                    <div className="h-3 bg-gray-100 rounded w-full" />
                  </div>
                  <div className="pt-4 border-t border-gray-100">
                    <div className="h-6 bg-green-100 rounded w-1/4 mb-3" />
                    <div className="flex flex-wrap gap-2">
                      <div className="h-6 bg-gray-100 rounded-full w-16" />
                      <div className="h-6 bg-gray-100 rounded-full w-20" />
                      <div className="h-6 bg-gray-100 rounded-full w-14" />
                      <div className="h-6 bg-gray-100 rounded-full w-18" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Floating badge */}
              <div className="absolute -bottom-4 -right-4 bg-green-500 text-white px-4 py-2 rounded-xl shadow-lg font-semibold text-sm">
                ATS Score: 95%
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between">
            <div className="flex items-center space-x-2 mb-4 md:mb-0">
              <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <span className="text-white font-bold">Talent Promo</span>
            </div>
            <div className="flex items-center space-x-6">
              <button
                onClick={() => setShowGuide(true)}
                className="hover:text-white transition-colors"
              >
                How It Works
              </button>
              <span className="text-sm">Demo by Vicki &middot; Data stays in your browser</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
