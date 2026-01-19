"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Header from "./components/layout/Header";
import OnboardingGuide from "./components/layout/OnboardingGuide";

const FIRST_VISIT_KEY = "talent_promo:first_visit";
const PENDING_INPUT_KEY = "talent_promo:pending_input";
const RECENT_LINKEDIN_KEY = "talent_promo:recent_linkedin";
const RECENT_JOB_KEY = "talent_promo:recent_job";
const MAX_RECENT = 2;

// Fun human verification questions - bots can't answer these!
const HUMAN_CHALLENGES = [
  { question: "What sound does a cat make?", answers: ["meow", "mew", "purr"] },
  { question: "What color is a ripe banana?", answers: ["yellow"] },
  { question: "How many legs does a dog have?", answers: ["4", "four"] },
  { question: "What do cows drink?", answers: ["water"] },  // Trick question - most say "milk"
  { question: "What's the opposite of 'hot'?", answers: ["cold", "cool"] },
  { question: "What day comes after Monday?", answers: ["tuesday", "tues"] },
  { question: "What do you call a baby dog?", answers: ["puppy", "pup"] },
  { question: "Is water wet? (yes/no)", answers: ["yes", "no", "both"] },  // Philosophy!
  { question: "What noise does a duck make?", answers: ["quack"] },
  { question: "How many eyes do you have?", answers: ["2", "two"] },
];

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
    color: "from-purple-500 to-pink-500",
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
  const [inputMode, setInputMode] = useState<"linkedin" | "paste">("linkedin");
  const [jobInputMode, setJobInputMode] = useState<"url" | "paste">("url");
  const [resumeText, setResumeText] = useState("");
  const [jobText, setJobText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [honeypot, setHoneypot] = useState("");  // Bot trap - should remain empty

  // Human verification challenge - initialize to 0 on server, randomize on client to avoid hydration mismatch
  const [challengeIndex, setChallengeIndex] = useState(0);
  const [challengeAnswer, setChallengeAnswer] = useState("");
  const [challengePassed, setChallengePassed] = useState(false);
  const currentChallenge = HUMAN_CHALLENGES[challengeIndex];

  // Recent URLs for quick selection
  const [recentLinkedin, setRecentLinkedin] = useState<string[]>([]);
  const [recentJob, setRecentJob] = useState<string[]>([]);
  const [showLinkedinDropdown, setShowLinkedinDropdown] = useState(false);
  const [showJobDropdown, setShowJobDropdown] = useState(false);
  const linkedinInputRef = useRef<HTMLInputElement>(null);
  const jobInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Randomize challenge on client side to avoid hydration mismatch
    setChallengeIndex(Math.floor(Math.random() * HUMAN_CHALLENGES.length));

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

  const checkChallengeAnswer = () => {
    const normalized = challengeAnswer.toLowerCase().trim();
    const isCorrect = currentChallenge.answers.some(a => normalized === a.toLowerCase());
    setChallengePassed(isCorrect);
    if (!isCorrect && challengeAnswer.trim()) {
      setError("Hmm, that doesn't seem right. Try again!");
    } else {
      setError("");
    }
    return isCorrect;
  };

  const canSubmit = () => {
    const hasProfile = inputMode === "linkedin"
      ? linkedinUrl && isValidUrl(linkedinUrl)
      : resumeText.trim().length > 50;
    const hasJob = jobInputMode === "url"
      ? jobUrl && isValidUrl(jobUrl)
      : jobText.trim().length > 50;
    return hasProfile && hasJob && challengePassed && !isSubmitting;
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
    };

    localStorage.setItem(PENDING_INPUT_KEY, JSON.stringify(inputData));

    // Navigate to optimize page
    router.push("/optimize");
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <Header showGuide={() => setShowGuide(true)} />

      <OnboardingGuide isOpen={showGuide} onClose={() => setShowGuide(false)} />

      {/* Hero Section with Input Form */}
      <section className="relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-0 -left-4 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob" />
          <div className="absolute top-0 -right-4 w-72 h-72 bg-yellow-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob animation-delay-2000" />
          <div className="absolute -bottom-8 left-20 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob animation-delay-4000" />
        </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left side - Headlines */}
            <div>
              {/* Badge */}
              <div className="inline-flex items-center px-4 py-1.5 rounded-full bg-indigo-100 text-indigo-700 text-sm font-medium mb-6">
                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                AI-Powered Resume Optimization
              </div>

              {/* Headline */}
              <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 tracking-tight mb-6">
                Land Your Dream Job with
                <span className="block text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
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
                  Free to use
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
                      LinkedIn URL
                    </span>
                  </button>
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
                      Paste Resume
                    </span>
                  </button>
                </div>

                {inputMode === "linkedin" ? (
                  <div className="relative">
                    <input
                      ref={linkedinInputRef}
                      type="url"
                      placeholder="https://linkedin.com/in/yourprofile"
                      value={linkedinUrl}
                      onChange={(e) => setLinkedinUrl(e.target.value)}
                      onFocus={() => setShowLinkedinDropdown(recentLinkedin.length > 0)}
                      onBlur={() => setTimeout(() => setShowLinkedinDropdown(false), 150)}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
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
                            className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 truncate"
                          >
                            {url}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <textarea
                    placeholder="Paste your resume text here..."
                    value={resumeText}
                    onChange={(e) => setResumeText(e.target.value)}
                    rows={4}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all resize-none"
                  />
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
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
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
                            className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 truncate"
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
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all resize-none"
                  />
                )}
              </div>

              {/* Human Verification - Fun challenge to stop bots */}
              <div className="mb-6 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl border border-purple-100">
                <div className="flex items-center mb-3">
                  <span className="text-lg mr-2">🤖</span>
                  <label className="text-sm font-medium text-gray-700">
                    Quick human check
                  </label>
                  {challengePassed && (
                    <span className="ml-2 text-green-600 text-sm font-medium flex items-center">
                      <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                      You&apos;re human!
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mb-2 italic">{currentChallenge.question}</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Your answer..."
                    value={challengeAnswer}
                    onChange={(e) => {
                      setChallengeAnswer(e.target.value);
                      if (challengePassed) setChallengePassed(false);  // Reset if they change answer
                    }}
                    onBlur={checkChallengeAnswer}
                    onKeyDown={(e) => e.key === "Enter" && checkChallengeAnswer()}
                    disabled={challengePassed}
                    className={`flex-1 px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all ${
                      challengePassed
                        ? "bg-green-50 border-green-300 text-green-700"
                        : "border-gray-200"
                    }`}
                  />
                  {!challengePassed && (
                    <button
                      type="button"
                      onClick={checkChallengeAnswer}
                      className="px-4 py-2 text-sm font-medium text-purple-700 bg-purple-100 rounded-lg hover:bg-purple-200 transition-all"
                    >
                      Check
                    </button>
                  )}
                </div>
              </div>

              {/* Submit Button */}
              <button
                onClick={handleSubmit}
                disabled={!canSubmit()}
                className="w-full py-4 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/40 disabled:shadow-none flex items-center justify-center"
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
                    <div className="flex-shrink-0 w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center text-indigo-600">
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
                    <div className="h-6 bg-indigo-100 rounded w-1/3 mb-3" />
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
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
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
              <span className="text-sm">Built with AI to help you present your best self</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
