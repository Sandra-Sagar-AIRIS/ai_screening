import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIRIS Frontend",
  description: "MVP dashboard for AIRIS recruiting platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
