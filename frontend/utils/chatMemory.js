import { getSupabaseClient } from "./supabase/client";

const CHAT_HISTORY_KEY = "medinsight:chatHistory";
const CHAT_SESSION_ID_KEY = "medinsight:chatSessionId";
const CHAT_MEMORY_TABLE = "medinsight_chat_memory";

export function getChatSessionId() {
  if (typeof window === "undefined") return "";

  const storedSessionId = localStorage.getItem(CHAT_SESSION_ID_KEY);
  if (storedSessionId) return storedSessionId;

  const sessionId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  localStorage.setItem(CHAT_SESSION_ID_KEY, sessionId);
  return sessionId;
}

export function startNewChatSession() {
  if (typeof window === "undefined") return "";

  const sessionId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  localStorage.setItem(CHAT_SESSION_ID_KEY, sessionId);
  sessionStorage.removeItem(CHAT_HISTORY_KEY);
  sessionStorage.removeItem("medinsight:lastQueryResult");
  return sessionId;
}

export async function loadChatMessages() {
  const fallbackMessages = loadLocalChatMessages();
  const supabase = getSupabaseClient();
  const sessionId = getChatSessionId();

  if (!supabase || !sessionId) {
    return fallbackMessages;
  }

  try {
    const { data, error } = await supabase
      .from(CHAT_MEMORY_TABLE)
      .select("messages")
      .eq("session_id", sessionId)
      .maybeSingle();

    if (error || !Array.isArray(data?.messages)) {
      return fallbackMessages;
    }

    writeLocalChatMessages(data.messages);
    return data.messages;
  } catch {
    return fallbackMessages;
  }
}

export async function saveChatMessages(messages) {
  writeLocalChatMessages(messages);

  const supabase = getSupabaseClient();
  const sessionId = getChatSessionId();

  if (!supabase || !sessionId) {
    return;
  }

  try {
    await supabase.from(CHAT_MEMORY_TABLE).upsert(
      {
        session_id: sessionId,
        messages,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "session_id" },
    );
  } catch {
    return;
  }
}

function loadLocalChatMessages() {
  if (typeof window === "undefined") return [];

  const storedHistory = sessionStorage.getItem(CHAT_HISTORY_KEY);
  if (!storedHistory) return [];

  try {
    const parsedHistory = JSON.parse(storedHistory);
    return Array.isArray(parsedHistory) ? parsedHistory : [];
  } catch {
    sessionStorage.removeItem(CHAT_HISTORY_KEY);
    return [];
  }
}

function writeLocalChatMessages(messages) {
  if (typeof window === "undefined") return;

  sessionStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(messages));
  const lastMessage = messages[messages.length - 1];
  if (lastMessage?.result) {
    sessionStorage.setItem("medinsight:lastQueryResult", JSON.stringify(lastMessage.result));
  }
}
