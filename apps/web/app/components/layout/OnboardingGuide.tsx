"use client";

import { useState } from "react";

interface OnboardingGuideProps {
  isOpen: boolean;
  onClose: () => void;
}

const steps = [
  {
    title: "Research",
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
    ),
    description: "We analyze your LinkedIn profile and the target job posting to understand requirements.",
    details: [
      "Fetches and parses your LinkedIn profile",
      "Extracts job requirements and tech stack",
      "Researches company culture and values",
      "Identifies gaps between your profile and the job",
    ],
  },
  {
    title: "Discovery",
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
        />
      </svg>
    ),
    description: "Through a guided conversation, we uncover hidden experiences that match job requirements.",
    details: [
      "Ask targeted questions about your experience",
      "Discover relevant skills you might have overlooked",
      "Extract quantifiable achievements",
      "Map your experiences to job requirements",
    ],
  },
  {
    title: "Drafting",
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
        />
      </svg>
    ),
    description: "We generate an ATS-optimized resume tailored specifically for your target job.",
    details: [
      "AI-generated professional resume",
      "Smart improvement suggestions",
      "Rich text editor for fine-tuning",
      "Version control with restore capability",
    ],
  },
  {
    title: "Export",
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
        />
      </svg>
    ),
    description: "Download your optimized resume in multiple formats with ATS analysis and LinkedIn tips.",
    details: [
      "PDF, Word, and plain text downloads",
      "ATS compatibility score and analysis",
      "LinkedIn profile optimization tips",
      "Keyword match report",
    ],
  },
];

export default function OnboardingGuide({ isOpen, onClose }: OnboardingGuideProps) {
  const [currentStep, setCurrentStep] = useState(0);

  if (!isOpen) return null;

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      onClose();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const step = steps[currentStep];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 transition-colors z-10"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {/* Progress dots */}
          <div className="absolute top-6 left-1/2 -translate-x-1/2 flex space-x-2">
            {steps.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentStep(index)}
                className={`w-2.5 h-2.5 rounded-full transition-all ${
                  index === currentStep
                    ? "bg-indigo-600 w-6"
                    : index < currentStep
                    ? "bg-indigo-300"
                    : "bg-gray-300"
                }`}
              />
            ))}
          </div>

          {/* Content */}
          <div className="pt-16 pb-8 px-8">
            {/* Step indicator */}
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl text-white mb-4">
                {step.icon}
              </div>
              <div className="text-sm font-medium text-indigo-600 mb-2">
                Step {currentStep + 1} of {steps.length}
              </div>
              <h2 className="text-2xl font-bold text-gray-900">{step.title}</h2>
            </div>

            {/* Description */}
            <p className="text-center text-gray-600 mb-8 text-lg">
              {step.description}
            </p>

            {/* Details */}
            <div className="bg-gray-50 rounded-xl p-6 mb-8">
              <h3 className="font-semibold text-gray-900 mb-4">What happens in this step:</h3>
              <ul className="space-y-3">
                {step.details.map((detail, index) => (
                  <li key={index} className="flex items-start">
                    <svg
                      className="w-5 h-5 text-indigo-500 mr-3 mt-0.5 flex-shrink-0"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    <span className="text-gray-700">{detail}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between">
              <button
                onClick={handlePrev}
                disabled={currentStep === 0}
                className={`px-6 py-2.5 rounded-lg font-medium transition-all ${
                  currentStep === 0
                    ? "text-gray-300 cursor-not-allowed"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                }`}
              >
                Previous
              </button>

              <button
                onClick={handleNext}
                className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors shadow-sm"
              >
                {currentStep === steps.length - 1 ? "Get Started" : "Next"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
