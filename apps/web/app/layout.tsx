import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Talent Promo",
  description: "Application to help talent to best present themselves",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
