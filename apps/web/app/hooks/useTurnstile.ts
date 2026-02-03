"use client";

import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Cloudflare Turnstile widget interface (from the global turnstile API).
 */
interface TurnstileWidgetApi {
  render: (
    container: string | HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "expired-callback"?: () => void;
      "error-callback"?: () => void;
      appearance?: "always" | "execute" | "interaction-only";
      theme?: "light" | "dark" | "auto";
    }
  ) => string;
  reset: (widgetId: string) => void;
  remove: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileWidgetApi;
  }
}

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";

export interface UseTurnstileReturn {
  /** The current Turnstile response token (null if not yet obtained). */
  token: string | null;
  /** Whether Turnstile is configured (site key is set). */
  isEnabled: boolean;
  /** Whether the widget is ready (token obtained, or Turnstile is disabled). */
  isReady: boolean;
  /** Whether there was an error rendering or verifying the widget. */
  hasError: boolean;
  /** Reset the widget to get a fresh token. */
  reset: () => void;
  /** Ref to attach to the container div where the widget renders. */
  containerRef: React.RefObject<HTMLDivElement | null>;
}

/**
 * React hook for managing Cloudflare Turnstile widget lifecycle.
 *
 * When NEXT_PUBLIC_TURNSTILE_SITE_KEY is not set, the hook returns
 * isReady=true immediately (dev bypass).
 */
export function useTurnstile(): UseTurnstileReturn {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [hasError, setHasError] = useState(false);

  const isEnabled = !!SITE_KEY;
  const isReady = !isEnabled || !!token;

  const renderWidget = useCallback(() => {
    if (!isEnabled || !containerRef.current || !window.turnstile) return;

    // Remove existing widget if any
    if (widgetIdRef.current) {
      try {
        window.turnstile.remove(widgetIdRef.current);
      } catch {
        // Widget may already be removed
      }
      widgetIdRef.current = null;
    }

    setToken(null);
    setHasError(false);

    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      sitekey: SITE_KEY,
      appearance: "interaction-only",
      theme: "light",
      callback: (newToken: string) => {
        setToken(newToken);
        setHasError(false);
      },
      "expired-callback": () => {
        setToken(null);
      },
      "error-callback": () => {
        setHasError(true);
        setToken(null);
      },
    });
  }, [isEnabled]);

  const reset = useCallback(() => {
    if (!isEnabled) return;

    if (widgetIdRef.current && window.turnstile) {
      try {
        window.turnstile.reset(widgetIdRef.current);
      } catch {
        // Widget may not be ready
      }
    }
    setToken(null);
    setHasError(false);
  }, [isEnabled]);

  // Render widget when the Turnstile script loads
  useEffect(() => {
    if (!isEnabled) return;

    // If the API is already loaded, render immediately
    if (window.turnstile) {
      renderWidget();
      return;
    }

    // Otherwise, poll for the API to become available (script loads async)
    const interval = setInterval(() => {
      if (window.turnstile) {
        clearInterval(interval);
        renderWidget();
      }
    }, 200);

    return () => {
      clearInterval(interval);
      // Cleanup widget on unmount
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          // Ignore cleanup errors
        }
        widgetIdRef.current = null;
      }
    };
  }, [isEnabled, renderWidget]);

  return {
    token,
    isEnabled,
    isReady,
    hasError,
    reset,
    containerRef,
  };
}
