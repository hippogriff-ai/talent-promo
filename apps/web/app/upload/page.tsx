"use client";

import { useRouter } from "next/navigation";
import FileUpload from "../components/FileUpload";

export default function UploadPage() {
  const router = useRouter();

  const handleUploadComplete = (fileId: string) => {
    console.log("Upload complete:", fileId);
    // Navigate to next step or show success message
    // router.push(`/process/${fileId}`);
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <FileUpload onUploadComplete={handleUploadComplete} />
    </div>
  );
}
