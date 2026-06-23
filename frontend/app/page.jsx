"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { saveChatMessages, startNewChatSession } from "../utils/chatMemory";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

function HeroMarkIcon({ className = "" }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M32 7 38.6 25.4H58L42.4 36.7 48.5 55 32 43.7 15.5 55 21.6 36.7 6 25.4h19.4L32 7Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3"
      />
      <circle cx="32" cy="32" r="9.5" stroke="currentColor" strokeWidth="3" />
      <path
        d="M22.5 32h19M32 22.5v19"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="3"
      />
    </svg>
  );
}

function SearchIcon({ className = "" }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="m20 20-4.2-4.2m1.7-5.1a6.8 6.8 0 1 1-13.5 0 6.8 6.8 0 0 1 13.5 0Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}

function ArrowRightIcon({ className = "" }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M5 12h14m-6-6 6 6-6 6"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}

function PillIcon({ type, className = "" }) {
  const paths = {
    verified: "M20 6 9 17l-5-5",
    books: "M5 5.5A2.5 2.5 0 0 1 7.5 3H20v16H7.5A2.5 2.5 0 0 0 5 21.5v-16Zm0 0v16M9 7h7M9 11h7",
    science: "M10 3h4M11 3v5.5L6.5 17A3 3 0 0 0 9.2 21h5.6a3 3 0 0 0 2.7-4L13 8.5V3M8.5 15h7",
  };

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d={paths[type]} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
    </svg>
  );
}

export default function LandingPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submitQuery(event) {
    event.preventDefault();

    const normalizedQuery = query.replace(/\s+/g, " ").trim();
    if (!normalizedQuery || isSubmitting) return;

    setError("");
    setIsSubmitting(true);

    try {
      const sessionId = startNewChatSession();
      const response = await fetch(`${API_BASE_URL}/query/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: normalizedQuery,
          session_id: sessionId,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || "MedInsight could not process that query.");
      }

      const firstMessage = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        result: payload,
      };
      await saveChatMessages([firstMessage]);
      router.push("/chat-continuation-ai");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "MedInsight request failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden bg-[#fdfcfb] text-[#151311]">
      <div className="medinsight-paper-pattern fixed inset-0 z-0 pointer-events-none" />

      <nav className="relative z-10 mx-auto flex h-20 w-full max-w-[1440px] items-center border-b border-[#cec5bd]/30 bg-[#faf9f8] px-4 md:px-16">
        <div className="flex items-center gap-4">
          <span className="font-serif-title text-2xl font-bold text-black">MedInsight</span>
        </div>
      </nav>

      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-4 py-20 md:px-16 md:py-24">
        <section className="flex w-full max-w-3xl flex-col items-center gap-8 text-center">
          <div className="mb-2 flex items-center justify-center">
            <HeroMarkIcon className="h-20 w-20 text-[#87ceeb]" />
          </div>

          <div>
            <h1 className="mb-4 font-serif-title text-[30px] leading-tight text-black md:text-[40px]">
              MedInsight
            </h1>
            <p className="font-sans-ui text-lg leading-relaxed text-[#4c4640]">
              Intelligent clinical research assistant
            </p>
          </div>

          <form className="mt-8 w-full max-w-2xl" onSubmit={submitQuery}>
            <div className="relative flex items-center">
              <SearchIcon className="pointer-events-none absolute left-6 h-5 w-5 text-[#4c4640]" />
              <input
                className="w-full rounded-full border border-[#87ceeb] bg-[#f5f3f0] py-4 pl-14 pr-16 font-sans-ui text-base leading-relaxed text-[#151311] shadow-sm transition-all placeholder:text-[#4c4640]/70 focus:outline-none focus:ring-1 focus:ring-[#87ceeb]"
                disabled={isSubmitting}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search clinical literature, trials, and protocols..."
                type="text"
                value={query}
              />
              <button
                aria-label="Search"
                className="absolute right-2 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-[#87ceeb] text-[#151311] transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!query.trim() || isSubmitting}
                type="submit"
              >
                {isSubmitting ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#151311]/30 border-t-[#151311]" />
                ) : (
                  <ArrowRightIcon className="h-5 w-5" />
                )}
              </button>
            </div>

            {error ? <p className="mt-3 text-center font-sans-ui text-sm text-[#ba1a1a]">{error}</p> : null}
          </form>

          <div className="mt-2 flex flex-wrap justify-center gap-4">
            {[
              ["verified", "Peer-reviewed evidence"],
              ["books", "Clinical research synthesis"],
              ["science", "Evidence-based answers"],
            ].map(([iconType, label]) => (
              <div
                className="flex min-h-10 items-center gap-2 rounded-full border border-[#87ceeb] bg-[#f5f3f0] px-4 py-2 font-sans-ui text-xs font-semibold uppercase leading-none tracking-wider text-[#151311] shadow-sm"
                key={label}
              >
                <PillIcon className="h-4 w-4 shrink-0 text-[#87ceeb]" type={iconType} />
                {label}
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="relative z-10 mt-auto w-full border-t border-[#cec5bd] bg-[#f4f3f2] py-12">
        <div className="mx-auto flex max-w-[1440px] flex-col items-center justify-between gap-6 px-4 md:flex-row md:px-16">
          <div className="font-serif-title text-2xl text-black">MedInsight</div>

          <div className="flex flex-wrap justify-center gap-6">
            {["Clinical Research Disclaimer", "Privacy Protocol", "Terms of Service", "Ethics Framework"].map(
              (item) => (
                <a
                  className="font-sans-ui text-xs font-semibold uppercase leading-none tracking-widest text-[#4c4640]/80 transition-opacity hover:text-black hover:opacity-100"
                  href="#"
                  key={item}
                >
                  {item}
                </a>
              ),
            )}
          </div>

          <div className="text-center font-sans-ui text-xs font-semibold uppercase leading-none tracking-widest text-[#4c4640] md:text-right">
            © 2026 MedInsight AI. For authorized clinical use only.
          </div>
        </div>
      </footer>
    </div>
  );
}
