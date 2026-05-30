"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";
import { useState } from "react";

import { saveChatMessages, startNewChatSession } from "../utils/chatMemory";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

function Icon({ children, className = "" }) {
  return <span className={`material-symbols-outlined ${className}`}>{children}</span>;
}

export default function LandingPage() {
  const router = useRouter();
  const textareaRef = useRef(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function resizeTextarea() {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
    if (textarea.scrollHeight > 200) {
      textarea.style.overflowY = "auto";
      textarea.style.height = "200px";
    } else {
      textarea.style.overflowY = "hidden";
    }
  }

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

  function submitOnEnter(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      submitQuery(event);
    }
  }

  return (
    <main className="relative flex h-screen flex-col overflow-hidden bg-[#0A0A0A]">
      <div className="absolute right-6 top-6 z-10 flex items-center gap-3 md:right-8 md:top-8">
        <button
          aria-label="Open menu"
          className="flex h-10 w-10 items-center justify-center rounded-full border border-outline-variant bg-[#141414] text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
          type="button"
        >
          <span aria-hidden="true" className="flex flex-col gap-1">
            <span className="block h-0.5 w-4 rounded-full bg-current" />
            <span className="block h-0.5 w-4 rounded-full bg-current" />
            <span className="block h-0.5 w-4 rounded-full bg-current" />
          </span>
        </button>
        <button
          aria-label="Open profile"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-primary font-body-sm text-body-sm font-bold text-on-primary shadow-lg transition-colors hover:bg-primary-fixed-dim"
          type="button"
        >
          JD
        </button>
      </div>

      <div className="custom-scrollbar flex-1 overflow-y-auto pb-40 pt-8">
        <div className="flex min-h-full flex-col items-center justify-center px-margin-mobile py-20 text-center">
          <h1 className="mb-2 font-headline-xl text-headline-xl tracking-normal text-primary">MedInsight</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Intelligent clinical research assistant
          </p>
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-0 left-0 right-0 p-6 md:p-8">
        <div className="pointer-events-auto mx-auto w-full max-w-3xl">
          <form
            className="rounded-xl border border-outline-variant bg-[#141414] p-4 shadow-2xl transition-all focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/20"
            onSubmit={submitQuery}
          >
            <div className="flex items-start gap-3">
              <textarea
                ref={textareaRef}
                className="custom-scrollbar w-full resize-none border-none bg-transparent py-2 font-body-md text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:ring-0"
                onInput={resizeTextarea}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={submitOnEnter}
                placeholder="Ask MedInsight clinical research questions..."
                rows={1}
                value={query}
              />
              <button
                aria-label="Search"
                className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-primary text-2xl font-semibold leading-none text-on-primary transition-colors hover:bg-primary-fixed-dim disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!query.trim() || isSubmitting}
                type="submit"
              >
                <span aria-hidden="true" className="-mt-0.5">
                  {isSubmitting ? "\u00b7" : "\u2191"}
                </span>
              </button>
            </div>
          </form>
          {error ? (
            <p className="mt-3 text-center font-body-sm text-body-sm text-error">{error}</p>
          ) : null}
          {isSubmitting ? (
            <div className="mt-4 flex justify-center" aria-label="Loading">
              <div className="h-7 w-7 animate-spin rounded-full border-2 border-outline-variant border-t-primary" />
            </div>
          ) : null}
          <p className="mt-3 text-center text-[10px] uppercase tracking-widest text-on-surface-variant/50">
            MedInsight AI utilizes verified peer-reviewed data. Verify critical clinical findings.
          </p>
        </div>
      </div>
    </main>
  );
}
