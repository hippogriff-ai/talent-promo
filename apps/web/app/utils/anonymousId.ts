/**
 * Anonymous ID utility for tracking user sessions without authentication.
 *
 * Generates a persistent anonymous ID stored in localStorage.
 * Used for:
 * - Preferences (writing style, formatting preferences)
 * - Ratings (draft quality feedback)
 * - Analytics (workflow usage patterns)
 */

const ANON_ID_KEY = "talent_promo:anonymous_id";

/**
 * Get the anonymous ID, creating one if it doesn't exist.
 *
 * @returns A persistent anonymous ID string
 */
export function getAnonymousId(): string {
  if (typeof window === "undefined") {
    // Server-side rendering - return a placeholder
    return "ssr-placeholder";
  }

  let id = localStorage.getItem(ANON_ID_KEY);
  if (!id) {
    id = `anon_${crypto.randomUUID().slice(0, 12)}`;
    localStorage.setItem(ANON_ID_KEY, id);
  }
  return id;
}

/**
 * Clear the anonymous ID (useful for "Start Fresh" functionality).
 */
export function clearAnonymousId(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(ANON_ID_KEY);
  }
}

/**
 * Check if an anonymous ID exists without creating one.
 */
export function hasAnonymousId(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return localStorage.getItem(ANON_ID_KEY) !== null;
}
