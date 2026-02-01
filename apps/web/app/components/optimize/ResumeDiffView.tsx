"use client";

import { useMemo } from "react";

interface ResumeDiffViewProps {
  originalHtml: string;
  optimizedHtml: string;
  onClose: () => void;
}

/**
 * ResumeDiffView - Shows a side-by-side comparison of original vs optimized resume.
 * Uses text extraction to compare content and highlights differences.
 */
export function ResumeDiffView({ originalHtml, optimizedHtml, onClose }: ResumeDiffViewProps) {
  // Extract text content from HTML for comparison
  const extractTextBlocks = (html: string): string[] => {
    if (!html) return [];
    // Create a temporary element to parse HTML
    const div = document.createElement("div");
    div.innerHTML = html;

    // Get all text-containing elements
    const blocks: string[] = [];
    const walker = document.createTreeWalker(
      div,
      NodeFilter.SHOW_ELEMENT,
      null
    );

    let node: Node | null = walker.currentNode;
    while (node) {
      const el = node as HTMLElement;
      const tagName = el.tagName?.toLowerCase();

      // Get block-level elements with text
      if (["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "span"].includes(tagName)) {
        const text = el.textContent?.trim();
        if (text && text.length > 0) {
          blocks.push(text);
        }
      }
      node = walker.nextNode();
    }

    return Array.from(new Set(blocks)); // Remove duplicates
  };

  // Compute differences
  const { originalBlocks, optimizedBlocks, additions, removals } = useMemo(() => {
    const original = extractTextBlocks(originalHtml);
    const optimized = extractTextBlocks(optimizedHtml);

    // Find additions (in optimized but not in original)
    const additions = optimized.filter(block => {
      // Check if this block or something very similar exists in original
      return !original.some(origBlock =>
        origBlock === block ||
        similarity(origBlock, block) > 0.8
      );
    });

    // Find removals (in original but not in optimized)
    const removals = original.filter(block => {
      return !optimized.some(optBlock =>
        optBlock === block ||
        similarity(block, optBlock) > 0.8
      );
    });

    return {
      originalBlocks: original,
      optimizedBlocks: optimized,
      additions,
      removals
    };
  }, [originalHtml, optimizedHtml]);

  // Simple similarity function (Jaccard-like)
  function similarity(str1: string, str2: string): number {
    if (!str1 || !str2) return 0;
    const words1 = new Set(str1.toLowerCase().split(/\s+/));
    const words2 = new Set(str2.toLowerCase().split(/\s+/));
    const intersection = Array.from(words1).filter(w => words2.has(w)).length;
    const union = new Set(Array.from(words1).concat(Array.from(words2))).size;
    return intersection / union;
  }

  // Stats
  const stats = {
    additions: additions.length,
    removals: removals.length,
    originalWordCount: originalBlocks.join(" ").split(/\s+/).length,
    optimizedWordCount: optimizedBlocks.join(" ").split(/\s+/).length,
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Resume Comparison</h2>
            <p className="text-sm text-gray-500 mt-1">
              Compare your original resume with the AI-optimized version
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Stats Bar */}
        <div className="flex items-center gap-6 px-6 py-3 bg-gray-50 border-b text-sm">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 bg-green-500 rounded"></span>
            <span className="text-gray-600">
              <span className="font-medium text-green-700">{stats.additions}</span> additions
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 bg-red-500 rounded"></span>
            <span className="text-gray-600">
              <span className="font-medium text-red-700">{stats.removals}</span> removals
            </span>
          </div>
          <div className="border-l border-gray-300 h-4"></div>
          <div className="text-gray-600">
            Word count: {stats.originalWordCount} → {stats.optimizedWordCount}
            {stats.optimizedWordCount > stats.originalWordCount && (
              <span className="text-green-600 ml-1">(+{stats.optimizedWordCount - stats.originalWordCount})</span>
            )}
            {stats.optimizedWordCount < stats.originalWordCount && (
              <span className="text-red-600 ml-1">({stats.optimizedWordCount - stats.originalWordCount})</span>
            )}
          </div>
        </div>

        {/* Content - Side by Side */}
        <div className="flex-1 overflow-hidden grid grid-cols-2 divide-x">
          {/* Original */}
          <div className="flex flex-col">
            <div className="px-4 py-2 bg-red-50 border-b border-red-100">
              <h3 className="font-medium text-red-800 text-sm">Original Resume</h3>
            </div>
            <div className="flex-1 overflow-auto p-4 text-sm">
              {originalBlocks.length > 0 ? (
                <div className="space-y-2">
                  {originalBlocks.map((block, idx) => {
                    const isRemoved = removals.includes(block);
                    return (
                      <p
                        key={idx}
                        className={`p-2 rounded ${
                          isRemoved
                            ? "bg-red-100 text-red-800 line-through"
                            : "text-gray-700"
                        }`}
                      >
                        {block}
                      </p>
                    );
                  })}
                </div>
              ) : (
                <div className="text-gray-400 italic">No original content available</div>
              )}
            </div>
          </div>

          {/* Optimized */}
          <div className="flex flex-col">
            <div className="px-4 py-2 bg-green-50 border-b border-green-100">
              <h3 className="font-medium text-green-800 text-sm">Optimized Resume</h3>
            </div>
            <div className="flex-1 overflow-auto p-4 text-sm">
              {optimizedBlocks.length > 0 ? (
                <div className="space-y-2">
                  {optimizedBlocks.map((block, idx) => {
                    const isAdded = additions.includes(block);
                    return (
                      <p
                        key={idx}
                        className={`p-2 rounded ${
                          isAdded
                            ? "bg-green-100 text-green-800 font-medium"
                            : "text-gray-700"
                        }`}
                      >
                        {isAdded && (
                          <span className="text-green-600 mr-1">+</span>
                        )}
                        {block}
                      </p>
                    );
                  })}
                </div>
              ) : (
                <div className="text-gray-400 italic">No optimized content available</div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex justify-between items-center">
          <p className="text-xs text-gray-500">
            Green highlights show new or enhanced content. Red strikethrough shows removed content.
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm"
          >
            Close Comparison
          </button>
        </div>
      </div>
    </div>
  );
}
