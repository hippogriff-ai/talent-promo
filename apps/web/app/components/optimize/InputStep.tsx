"use client";

import { useState } from "react";

interface InputStepProps {
  inputData: {
    linkedinUrl?: string;
    jobUrl?: string;
    resumeText?: string;
  };
  setInputData: (data: {
    linkedinUrl?: string;
    jobUrl?: string;
    resumeText?: string;
  }) => void;
  onStart: () => void;
}

export default function InputStep({
  inputData,
  setInputData,
  onStart,
}: InputStepProps) {
  const [inputMode, setInputMode] = useState<"linkedin" | "paste">("linkedin");

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-3xl font-bold text-gray-900">
          Optimize Your Resume
        </h2>
        <p className="mt-2 text-gray-600">
          Enter your profile and target job to get started
        </p>
      </div>

      {/* Profile Input */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h3 className="text-lg font-semibold text-gray-900">Your Profile</h3>

        {/* Toggle */}
        <div className="flex space-x-2">
          <button
            onClick={() => setInputMode("linkedin")}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${
              inputMode === "linkedin"
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            LinkedIn URL
          </button>
          <button
            onClick={() => setInputMode("paste")}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${
              inputMode === "paste"
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            Paste Resume
          </button>
        </div>

        {inputMode === "linkedin" ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              LinkedIn Profile URL
            </label>
            <input
              type="url"
              placeholder="https://linkedin.com/in/yourprofile"
              value={inputData.linkedinUrl || ""}
              onChange={(e) =>
                setInputData({ ...inputData, linkedinUrl: e.target.value })
              }
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="mt-1 text-sm text-gray-500">
              We&apos;ll fetch your profile and extract your experience
            </p>
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Paste Your Resume
            </label>
            <textarea
              placeholder="Paste your resume text here..."
              value={inputData.resumeText || ""}
              onChange={(e) =>
                setInputData({ ...inputData, resumeText: e.target.value })
              }
              rows={10}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
            />
          </div>
        )}
      </div>

      {/* Job Input */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h3 className="text-lg font-semibold text-gray-900">Target Job</h3>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Job Posting URL
          </label>
          <input
            type="url"
            placeholder="https://jobs.example.com/software-engineer"
            value={inputData.jobUrl || ""}
            onChange={(e) =>
              setInputData({ ...inputData, jobUrl: e.target.value })
            }
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <p className="mt-1 text-sm text-gray-500">
            We&apos;ll analyze the job requirements and tailor your resume
          </p>
        </div>
      </div>

      {/* Start Button */}
      <div className="flex justify-center">
        <button
          onClick={onStart}
          disabled={
            !inputData.jobUrl ||
            (!inputData.linkedinUrl && !inputData.resumeText)
          }
          className="px-8 py-4 bg-blue-600 text-white rounded-lg font-semibold text-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          Start Optimization
        </button>
      </div>

      {/* Info */}
      <div className="text-center text-sm text-gray-500 space-y-1">
        <p>This process typically takes 2-5 minutes</p>
        <p>
          You&apos;ll have the opportunity to review and edit before exporting
        </p>
      </div>
    </div>
  );
}
