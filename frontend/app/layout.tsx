import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AIRIS Frontend",
  description: "MVP dashboard for AIRIS recruiting platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} font-sans`}>
      <body className="antialiased text-slate-900">
        {children}
        {/* Dev-only Tailwind probe — remove after confirming utilities load */}
        {process.env.NODE_ENV === "development" ? (
          <div
            aria-hidden
            className="pointer-events-none fixed bottom-3 right-3 z-[9999] rounded-md bg-red-600 px-3 py-2 text-xs font-semibold text-white shadow-lg print:hidden"
            data-tailwind-probe="true"
          >
            Tailwind OK
          </div>
        ) : null}
      </body>
    </html>
  );
}
