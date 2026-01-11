"use client";

interface DownloadLink {
  format: string;
  label: string;
  url: string;
}

interface CompletionScreenProps {
  downloads: DownloadLink[];
  onStartNew: () => void;
  atsScore?: number;
  linkedinOptimized?: boolean;
}

/**
 * Final completion screen shown when workflow is fully complete.
 * Shows success message, download links, and "Start New" option.
 */
export default function CompletionScreen({
  downloads,
  onStartNew,
  atsScore,
  linkedinOptimized,
}: CompletionScreenProps) {
  return (
    <div className="max-w-2xl mx-auto">
      {/* Success Header */}
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-10 h-10 text-green-600"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Resume Optimization Complete!
        </h1>
        <p className="text-gray-600">
          Your tailored resume is ready for download
        </p>
      </div>

      {/* Stats */}
      {(atsScore !== undefined || linkedinOptimized) && (
        <div className="grid grid-cols-2 gap-4 mb-8">
          {atsScore !== undefined && (
            <div className="bg-white rounded-lg border p-4 text-center">
              <div className="text-3xl font-bold text-green-600 mb-1">
                {atsScore}%
              </div>
              <div className="text-sm text-gray-600">ATS Compatibility</div>
            </div>
          )}
          {linkedinOptimized && (
            <div className="bg-white rounded-lg border p-4 text-center">
              <div className="flex items-center justify-center mb-1">
                <svg
                  className="w-8 h-8 text-blue-600"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" />
                </svg>
              </div>
              <div className="text-sm text-gray-600">LinkedIn Ready</div>
            </div>
          )}
        </div>
      )}

      {/* Downloads */}
      <div className="bg-white rounded-lg border overflow-hidden mb-8">
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h2 className="font-medium text-gray-900">Download Your Resume</h2>
        </div>
        <div className="divide-y">
          {downloads.map((download) => (
            <a
              key={download.format}
              href={download.url}
              download
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center">
                <FileIcon format={download.format} />
                <span className="ml-3 font-medium text-gray-900">
                  {download.label}
                </span>
              </div>
              <svg
                className="w-5 h-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
            </a>
          ))}
        </div>
      </div>

      {/* Next Steps */}
      <div className="bg-blue-50 rounded-lg p-4 mb-8">
        <h3 className="font-medium text-blue-900 mb-2">Next Steps</h3>
        <ul className="text-sm text-blue-800 space-y-2">
          <li className="flex items-start">
            <span className="mr-2">1.</span>
            Download your resume in PDF format for online applications
          </li>
          <li className="flex items-start">
            <span className="mr-2">2.</span>
            Use the DOCX version if you need to make additional edits
          </li>
          <li className="flex items-start">
            <span className="mr-2">3.</span>
            Update your LinkedIn profile with the suggested improvements
          </li>
          <li className="flex items-start">
            <span className="mr-2">4.</span>
            Review the ATS report for any final optimizations
          </li>
        </ul>
      </div>

      {/* Start New */}
      <div className="text-center">
        <p className="text-gray-600 mb-4">
          Ready to optimize for another job?
        </p>
        <button
          onClick={onStartNew}
          className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          Start New Application
        </button>
      </div>
    </div>
  );
}

/**
 * File type icon component.
 */
function FileIcon({ format }: { format: string }) {
  const colors: Record<string, string> = {
    pdf: "text-red-500 bg-red-50",
    docx: "text-blue-500 bg-blue-50",
    txt: "text-gray-500 bg-gray-100",
    json: "text-green-500 bg-green-50",
  };

  const colorClass = colors[format.toLowerCase()] || colors.txt;

  return (
    <div
      className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorClass}`}
    >
      <span className="text-xs font-bold uppercase">{format}</span>
    </div>
  );
}
