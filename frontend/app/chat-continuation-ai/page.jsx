"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { getChatSessionId, loadChatMessages, saveChatMessages } from "../../utils/chatMemory";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

const emptyResult = {
  original_query: "Ask a clinical research question from the landing page",
  cleaned_keywords: [],
  papers: [],
  retrieved_chunks: [],
  answer: "Submit a query from the MedInsight landing page to generate an evidence-based answer.",
};

function makeMessage(result) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    result,
  };
}

function parseInlineFormatting(text) {
  const parts = [];
  const pattern = /(\*\*[^*]+\*\*|<sup>.*?<\/sup>)/g;
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];
    if (token.startsWith("**")) {
      parts.push(
        <strong key={`${match.index}-strong`} className="font-semibold text-black">
          {token.slice(2, -2)}
        </strong>,
      );
    } else {
      parts.push(<sup key={`${match.index}-sup`}>{token.replace(/<\/?sup>/g, "")}</sup>);
    }

    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length ? parts : text;
}

function buildAnswerBlocks(answer) {
  const blocks = [];
  let bulletItems = [];

  function flushBullets() {
    if (!bulletItems.length) return;

    blocks.push({ type: "list", items: bulletItems });
    bulletItems = [];
  }

  String(answer || "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .forEach((line) => {
      if (!line) {
        flushBullets();
        return;
      }

      const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
      if (headingMatch) {
        flushBullets();
        blocks.push({
          type: "heading",
          level: headingMatch[1].length,
          text: headingMatch[2].replace(/#+$/g, "").trim(),
        });
        return;
      }

      const bulletMatch = line.match(/^[-*]\s+(.+)$/);
      if (bulletMatch) {
        bulletItems.push(bulletMatch[1]);
        return;
      }

      flushBullets();
      blocks.push({ type: "paragraph", text: line.replace(/^#+\s*/, "") });
    });

  flushBullets();
  return blocks;
}

function AnswerContent({ answer }) {
  const blocks = buildAnswerBlocks(answer);

  return blocks.map((block, index) => {
    if (block.type === "heading") {
      const headingClass =
        block.level <= 1
          ? "mt-7 first:mt-0 font-serif-title text-2xl text-black"
          : block.level === 2
            ? "mt-6 font-sans-ui text-lg font-semibold text-indigo-700"
            : "mt-4 font-sans-ui text-base font-semibold text-indigo-700";

      return (
        <h2 key={`${block.text}-${index}`} className={headingClass}>
          {parseInlineFormatting(block.text)}
        </h2>
      );
    }

    if (block.type === "list") {
      return (
        <ul key={`list-${index}`} className="ml-5 list-disc space-y-2">
          {block.items.map((item, itemIndex) => (
            <li key={`${item}-${itemIndex}`}>{parseInlineFormatting(item)}</li>
          ))}
        </ul>
      );
    }

    return <p key={`${block.text}-${index}`}>{parseInlineFormatting(block.text)}</p>;
  });
}

export default function ChatContinuationPage() {
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    let isMounted = true;

    async function restoreMessages() {
      const storedMessages = await loadChatMessages();
      if (!isMounted) return;

      if (storedMessages.length) {
        setMessages(storedMessages);
        return;
      }

      const storedResult = sessionStorage.getItem("medinsight:lastQueryResult");
      if (!storedResult) {
        setMessages([makeMessage(emptyResult)]);
        return;
      }

      try {
        const firstMessage = makeMessage(JSON.parse(storedResult));
        if (isMounted) {
          setMessages([firstMessage]);
          void saveChatMessages([firstMessage]);
          return;
        }
      } catch {
        if (isMounted) {
          setMessages([makeMessage(emptyResult)]);
        }
      }
    }

    restoreMessages();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isSubmitting]);

  async function submitPrompt(event) {
    event.preventDefault();

    const normalizedPrompt = prompt.replace(/\s+/g, " ").trim();
    if (!normalizedPrompt || isSubmitting) return;

    setError("");
    setIsSubmitting(true);

    try {
      // Send the last ≤5 turns directly so the backend has conversation
      // context without relying on a Supabase read succeeding first.
      const historySnapshot = messages.slice(-5).flatMap((message) => {
        const q = message?.result?.original_query;
        const a = message?.result?.answer;
        return q && a ? [{ query: q, answer: a }] : [];
      });

      const response = await fetch(`${API_BASE_URL}/query/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: normalizedPrompt,
          session_id: getChatSessionId(),
          conversation_history: historySnapshot,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || "MedInsight could not process that query.");
      }

      const nextMessage = makeMessage(payload);
      setMessages((currentMessages) => {
        const nextMessages = [...currentMessages, nextMessage];
        void saveChatMessages(nextMessages);
        return nextMessages;
      });
      setPrompt("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "MedInsight request failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function submitOnEnter(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      submitPrompt(event);
    }
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#fdfcfb] text-[#151311]">
      <header className="flex h-16 flex-shrink-0 items-center justify-between border-b border-[#cec5bd]/50 bg-[#faf9f8] px-margin-mobile md:px-margin-desktop">
        <div className="flex items-center gap-8">
          <Link className="font-serif-title text-2xl font-bold tracking-normal text-black" href="/">
            MedInsight
          </Link>
        </div>
        <div className="flex items-center gap-4">
          <Link
            className="rounded bg-[#87ceeb] px-4 py-2 font-sans-ui text-xs font-semibold uppercase tracking-widest text-[#151311] duration-100 hover:opacity-80 active:scale-95"
            href="/"
          >
            New Search
          </Link>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <main className="custom-scrollbar min-w-0 flex-1 overflow-y-auto px-margin-mobile pb-36 pt-8 md:px-0">
          <div className="mx-auto flex max-w-[900px] flex-col gap-12">
            {messages.map((message) => (
              <ChatTurn key={message.id} result={message.result} />
            ))}

            <div ref={scrollRef} />
          </div>
        </main>
      </div>

      <div className="pointer-events-none fixed bottom-0 left-0 w-full bg-gradient-to-t from-[#fdfcfb] via-[#fdfcfb]/95 to-transparent p-6 md:p-8">
        <form className="pointer-events-auto mx-auto max-w-[800px]" onSubmit={submitPrompt}>
          <div className="flex items-center gap-2 rounded-full border border-[#87ceeb] bg-[#f5f3f0] p-2 shadow-lg transition-all focus-within:ring-1 focus-within:ring-[#87ceeb]">
            <input
              className="min-w-0 flex-grow border-none bg-transparent px-4 py-3 font-sans-ui text-[#151311] placeholder:text-[#4c4640]/60 focus:ring-0"
              disabled={isSubmitting}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={submitOnEnter}
              placeholder="Ask a follow-up question..."
              type="text"
              value={prompt}
            />
            <button
              aria-label="Send follow-up"
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-[#87ceeb] text-2xl font-semibold leading-none text-[#151311] transition-all hover:opacity-80 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!prompt.trim() || isSubmitting}
              type="submit"
            >
              <span aria-hidden="true" className="-mt-0.5">
                {isSubmitting ? "\u00b7" : "\u2191"}
              </span>
            </button>
          </div>
          {error ? <p className="mt-3 text-center text-body-sm text-[#ba1a1a]">{error}</p> : null}
          {isSubmitting ? (
            <div className="mt-4 flex justify-center" aria-label="Loading">
              <div className="h-7 w-7 animate-spin rounded-full border-2 border-[#cec5bd] border-t-[#87ceeb]" />
            </div>
          ) : null}
        </form>
      </div>
    </div>
  );
}

function ChatTurn({ result }) {
  return (
    <section className="flex flex-col gap-6 border-b border-[#cec5bd]/60 pb-12 last:border-b-0">
      <h1 className="font-serif-title text-3xl tracking-normal text-black">
        {result.original_query}
      </h1>

      <article className="space-y-4 font-sans-ui text-base leading-relaxed text-[#151311]">
        <AnswerContent answer={result.answer} />
      </article>
    </section>
  );
}
