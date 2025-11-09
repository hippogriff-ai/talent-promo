"use client";

import { useState } from "react";
import ResumeUpload from "../components/ResumeUpload";
import JobURLInput from "../components/JobURLInput";

type Tab = "resume" | "job";

export default function UploadPage() {
  const [activeTab, setActiveTab] = useState<Tab>("resume");

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-7xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Talent Application Tools
          </h1>
          <p className="text-lg text-gray-600">
            Parse resumes and retrieve job postings with ease
          </p>
        </div>

        {/* Tabs */}
        <div className="flex justify-center mb-8">
          <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1">
            <button
              onClick={() => setActiveTab("resume")}
              className={`px-6 py-3 rounded-md font-medium transition-colors ${
                activeTab === "resume"
                  ? "bg-blue-600 text-white"
                  : "text-gray-700 hover:text-gray-900"
              }`}
            >
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                Resume Parser
              </div>
            </button>
            <button
              onClick={() => setActiveTab("job")}
              className={`px-6 py-3 rounded-md font-medium transition-colors ${
                activeTab === "job"
                  ? "bg-blue-600 text-white"
                  : "text-gray-700 hover:text-gray-900"
              }`}
            >
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
                Job Retriever
              </div>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="transition-all duration-200">
          {activeTab === "resume" ? <ResumeUpload /> : <JobURLInput />}
        </div>

        {/* Features Section */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
              Resume Parser Features
            </h3>
            <ul className="space-y-2 text-gray-700">
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                Supports PDF and DOCX formats (up to 5MB)
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                Extracts structured data (work, education, skills)
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                Stores data locally with IndexedDB
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                View and edit parsed results
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                Export as JSON
              </li>
            </ul>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
              </svg>
              Job Retriever Features
            </h3>
            <ul className="space-y-2 text-gray-700">
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                Supports LinkedIn, Indeed, Glassdoor & more
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                Extracts job title, company, requirements, salary
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                Batch processing for multiple URLs
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                Caches results for faster retrieval
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                View structured job data
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
