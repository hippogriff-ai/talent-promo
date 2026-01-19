"use client";

import { useState } from "react";

interface PreferenceRatingProps {
  step: string;
  onRate: (preference: "A" | "B" | "tie", reason?: string) => void;
  disabled?: boolean;
}

export function PreferenceRating({ step, onRate, disabled }: PreferenceRatingProps) {
  const [selected, setSelected] = useState<"A" | "B" | "tie" | null>(null);
  const [reason, setReason] = useState("");

  const handleSubmit = () => {
    if (selected) {
      onRate(selected, reason || undefined);
      setSelected(null);
      setReason("");
    }
  };

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h4 className="font-medium mb-3">Rate: {step}</h4>

      <div className="flex gap-2 mb-3">
        {(["A", "B", "tie"] as const).map((pref) => (
          <button
            key={pref}
            onClick={() => setSelected(pref)}
            disabled={disabled}
            className={`flex-1 py-2 px-4 rounded border transition-colors ${
              selected === pref
                ? pref === "A"
                  ? "bg-blue-600 text-white border-blue-600"
                  : pref === "B"
                  ? "bg-purple-600 text-white border-purple-600"
                  : "bg-gray-600 text-white border-gray-600"
                : "bg-white hover:bg-gray-50 border-gray-300"
            } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            {pref === "tie" ? "Tie" : `Variant ${pref}`}
          </button>
        ))}
      </div>

      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Optional: Why did you choose this? (helps improve the system)"
        className="w-full px-3 py-2 border rounded text-sm mb-3"
        rows={2}
        disabled={disabled}
      />

      <button
        onClick={handleSubmit}
        disabled={!selected || disabled}
        className="w-full bg-green-600 text-white py-2 rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Submit Rating
      </button>
    </div>
  );
}
