"use client";

import { useState, useEffect, useRef } from "react";

interface UseTypingEffectOptions {
  /** Speed in milliseconds per character (lower = faster) */
  speed?: number;
  /** Initial delay before typing starts */
  delay?: number;
  /** Callback when typing completes */
  onComplete?: () => void;
  /** Whether to skip the effect and show text immediately */
  skip?: boolean;
}

interface UseTypingEffectReturn {
  /** Current displayed text */
  displayedText: string;
  /** Whether typing is in progress */
  isTyping: boolean;
  /** Whether typing has completed */
  isComplete: boolean;
  /** Skip to end immediately */
  skipToEnd: () => void;
}

/**
 * Hook for typing animation effect.
 * Displays text character by character to create a typewriter effect.
 *
 * @param fullText - The complete text to type out
 * @param options - Configuration options
 */
export function useTypingEffect(
  fullText: string,
  options: UseTypingEffectOptions = {}
): UseTypingEffectReturn {
  const { speed = 15, delay = 0, onComplete, skip = false } = options;

  const [displayedText, setDisplayedText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const indexRef = useRef(0);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Reset when fullText changes
  useEffect(() => {
    if (skip) {
      setDisplayedText(fullText);
      setIsTyping(false);
      setIsComplete(true);
      return;
    }

    // Reset state for new text
    indexRef.current = 0;
    setDisplayedText("");
    setIsComplete(false);

    if (!fullText) {
      return;
    }

    // Start typing after delay
    const startTyping = () => {
      setIsTyping(true);
    };

    const delayTimeout = setTimeout(startTyping, delay);

    return () => {
      clearTimeout(delayTimeout);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [fullText, delay, skip]);

  // Typing animation loop
  useEffect(() => {
    if (!isTyping || isComplete || skip) {
      return;
    }

    if (indexRef.current >= fullText.length) {
      setIsTyping(false);
      setIsComplete(true);
      onComplete?.();
      return;
    }

    // Type next character
    const typeNextChar = () => {
      // Type multiple characters at once for faster perceived speed
      // but still maintain the typing feel
      const charsToAdd = getCharsToAdd(fullText, indexRef.current);
      indexRef.current += charsToAdd;
      setDisplayedText(fullText.slice(0, indexRef.current));
    };

    timeoutRef.current = setTimeout(typeNextChar, speed);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [isTyping, displayedText, fullText, speed, isComplete, onComplete, skip]);

  const skipToEnd = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    indexRef.current = fullText.length;
    setDisplayedText(fullText);
    setIsTyping(false);
    setIsComplete(true);
    onComplete?.();
  };

  return {
    displayedText,
    isTyping,
    isComplete,
    skipToEnd,
  };
}

/**
 * Determine how many characters to add at once.
 * This creates a more natural typing feel by:
 * - Adding multiple characters at once for faster perceived speed
 * - Pausing slightly at punctuation
 */
function getCharsToAdd(text: string, currentIndex: number): number {
  if (currentIndex >= text.length) return 0;

  const char = text[currentIndex];

  // Single char for punctuation (creates natural pauses)
  if (['.', ',', '!', '?', ':', ';', '-'].includes(char)) {
    return 1;
  }

  // Add 2-3 chars at once for regular characters (feels faster)
  const remaining = text.length - currentIndex;
  return Math.min(2, remaining);
}

export default useTypingEffect;
