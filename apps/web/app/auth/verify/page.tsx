"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/app/hooks/useAuth";

const STORAGE_KEYS = {
  preferences: "resume_agent:preferences",
  pendingEvents: "resume_agent:pending_events",
  pendingRatings: "resume_agent:pending_ratings",
  anonymousId: "resume_agent:anonymous_id",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function VerifyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { verify, isAuthenticated } = useAuth();
  const [status, setStatus] = useState<"verifying" | "success" | "error" | "migrating">("verifying");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");

    if (!token) {
      setStatus("error");
      setMessage("No verification token provided.");
      return;
    }

    if (isAuthenticated) {
      router.push("/");
      return;
    }

    const verifyToken = async () => {
      const result = await verify(token);

      if (result.success) {
        // Check for anonymous data to migrate
        const hasAnonymousData = checkForAnonymousData();

        if (hasAnonymousData) {
          setStatus("migrating");
          setMessage("Migrating your saved preferences...");
          await migrateAnonymousData();
        }

        setStatus("success");
        setMessage("Successfully signed in! Redirecting...");

        // Redirect after short delay
        setTimeout(() => {
          router.push("/");
        }, 1500);
      } else {
        setStatus("error");
        setMessage(result.message);
      }
    };

    verifyToken();
  }, [searchParams, verify, router, isAuthenticated]);

  const checkForAnonymousData = () => {
    try {
      const preferences = localStorage.getItem(STORAGE_KEYS.preferences);
      const events = localStorage.getItem(STORAGE_KEYS.pendingEvents);
      const ratings = localStorage.getItem(STORAGE_KEYS.pendingRatings);
      const anonymousId = localStorage.getItem(STORAGE_KEYS.anonymousId);

      return !!(anonymousId && (preferences || events || ratings));
    } catch {
      return false;
    }
  };

  const migrateAnonymousData = async () => {
    try {
      const anonymousId = localStorage.getItem(STORAGE_KEYS.anonymousId);
      if (!anonymousId) return;

      const preferences = localStorage.getItem(STORAGE_KEYS.preferences);
      const events = localStorage.getItem(STORAGE_KEYS.pendingEvents);
      const ratings = localStorage.getItem(STORAGE_KEYS.pendingRatings);

      const migrationData = {
        anonymous_id: anonymousId,
        preferences: preferences ? JSON.parse(preferences) : null,
        events: events ? JSON.parse(events) : [],
        ratings: ratings ? JSON.parse(ratings) : [],
      };

      const response = await fetch(`${API_URL}/api/auth/migrate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(migrationData),
        credentials: "include",
      });

      if (response.ok) {
        // Clear migrated data from localStorage
        localStorage.removeItem(STORAGE_KEYS.preferences);
        localStorage.removeItem(STORAGE_KEYS.pendingEvents);
        localStorage.removeItem(STORAGE_KEYS.pendingRatings);
        localStorage.removeItem(STORAGE_KEYS.anonymousId);
      }
    } catch (error) {
      console.error("Migration error:", error);
      // Continue even if migration fails - data stays in localStorage
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 text-center">
        {status === "verifying" && (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="text-gray-600">Verifying your login...</p>
          </>
        )}

        {status === "migrating" && (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
            <p className="text-gray-600">{message}</p>
          </>
        )}

        {status === "success" && (
          <>
            <div className="text-green-500 text-5xl">✓</div>
            <p className="text-green-800">{message}</p>
          </>
        )}

        {status === "error" && (
          <>
            <div className="text-red-500 text-5xl">✗</div>
            <p className="text-red-800 mb-4">{message}</p>
            <Link
              href="/auth/login"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
            >
              Try again
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      }
    >
      <VerifyContent />
    </Suspense>
  );
}
