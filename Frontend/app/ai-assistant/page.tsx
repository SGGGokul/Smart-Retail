"use client";

import { useState, useRef, useEffect } from "react";
import PageHeader from "@/components/dashboard/PageHeader";
import NoticeBanner from "@/components/ui/NoticeBanner";
import MaterialIcon from "@/components/ui/MaterialIcon";
import { sendChatMessage } from "@/lib/api/assistant";
import { isRetailDomainQuery, DOMAIN_REJECTION_MESSAGE } from "@/lib/assistant";
import { getDashboardSummary } from "@/lib/api/dashboard";
import type { AnalyticsSummaryResponse } from "@/types/dashboard";

let messageSequence = 0;
function createMessageId(): string {
  messageSequence += 1;
  return `msg-${messageSequence}`;
}

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  time: string;
  suggestedFollowUps?: string[];
  isError?: boolean;
  source?: string;
}

const STARTER_PROMPTS = [
  { label: "How many customers visited today?", icon: "trending_up" },
  { label: "Which shelves need restocking?", icon: "inventory_2" },
  { label: "What is the longest checkout queue?", icon: "schedule" },
  { label: "Summarize today's alerts.", icon: "warning" },
];

export default function AiAssistantPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>("conv-session-104");
  const [notice, setNotice] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [backendSummary, setBackendSummary] = useState<AnalyticsSummaryResponse | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatScrollContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch genuine summary telemetry on mount for status banner
  useEffect(() => {
    const controller = new AbortController();
    getDashboardSummary(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setBackendSummary(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setBackendSummary(null);
      });

    return () => {
      controller.abort();
    };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages, isLoading]);

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || inputMessage).trim();
    if (!query || isLoading) return;

    const userMsg: ChatMessage = {
      id: createMessageId(),
      sender: "user",
      text: query,
      time: "Just now",
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputMessage("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    // Domain restriction: reject non-retail queries before calling the API
    if (!isRetailDomainQuery(query)) {
      const rejectionMsg: ChatMessage = {
        id: createMessageId(),
        sender: "assistant",
        text: DOMAIN_REJECTION_MESSAGE,
        suggestedFollowUps: [
          "How many customers visited today?",
          "Which shelves need restocking?",
          "What is the longest checkout queue?",
          "Summarize today's alerts.",
        ],
        source: "Domain Validation",
        time: "Just now",
      };
      setMessages((prev) => [...prev, rejectionMsg]);
      return;
    }

    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        message: query,
        conversationId,
      });

      if (response && response.conversationId) {
        setConversationId(response.conversationId);
      }

      const assistantMsg: ChatMessage = {
        id: createMessageId(),
        sender: "assistant",
        text: response.answer || "No response text returned by assistant.",
        suggestedFollowUps: response.suggestedFollowUps,
        source: "FastAPI Assistant Service",
        time: "Just now",
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      // Show genuine offline / connection state, DO NOT substitute with fake answers!
      const errorMsg: ChatMessage = {
        id: createMessageId(),
        sender: "assistant",
        text: `Unable to connect to the assistant service on the FastAPI backend (POST /api/v1/assistant/chat). Please check that your FastAPI server is running on http://localhost:8000.\n\nError: ${(err as Error).message}`,
        isError: true,
        source: "Connection Error",
        time: "Just now",
        suggestedFollowUps: [
          "Check system health in Settings",
          "Retry request",
        ],
      };

      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputMessage(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  const handleClearHistory = () => {
    setMessages([]);
    setConversationId(`conv-${Date.now()}`);
    setNotice("Conversation session cleared.");
    setTimeout(() => setNotice(null), 2500);
  };

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <PageHeader
        title="RetailIQ Copilot"
        description="Natural language queries for store footfall analytics, inventory replenishment, and checkout queues."
        actions={
          <button
            type="button"
            onClick={handleClearHistory}
            aria-label="Reset conversation session"
            className="flex items-center gap-1.5 rounded-lg border border-[#e6e7e3] bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-[#f8f8f6] hover:text-slate-900 transition-colors shadow-2xs cursor-pointer"
          >
            <MaterialIcon name="refresh" className="h-3.5 w-3.5 text-slate-600" aria-hidden="true" />
            <span>Reset Chat</span>
          </button>
        }
      />

      {notice && (
        <NoticeBanner
          type="info"
          message={notice}
          onDismiss={() => setNotice(null)}
        />
      )}

      {/* Conversation Workspace */}
      <div className="max-w-4xl mx-auto">
        <section
          aria-label="RetailIQ Copilot conversation workspace"
          className="relative flex flex-col rounded-3xl border border-[#e6e7e3] bg-white h-[680px] sm:h-[720px] shadow-2xs overflow-hidden"
        >
          {/* Subtle Ambient Emerald Glow */}
          <div
            className="pointer-events-none absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 h-80 w-80 rounded-full bg-emerald-100/40 blur-3xl -z-0"
            aria-hidden="true"
          />

          {/* Clean Top Bar */}
          <div className="relative z-10 flex items-center justify-between border-b border-[#eeefec] px-4 sm:px-6 py-2.5 bg-white/80 backdrop-blur-xs shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-950 text-emerald-300 shadow-2xs">
                <MaterialIcon name="smart_toy" className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="flex items-center gap-2">
                <h2 className="text-xs sm:text-sm font-bold text-slate-900">
                  RetailIQ Copilot
                </h2>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-900 border border-emerald-200">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
                  <span>FastAPI Assistant Target</span>
                </span>
              </div>
            </div>

            {messages.length > 0 && (
              <button
                type="button"
                onClick={handleClearHistory}
                className="flex items-center gap-1 text-[11px] font-semibold text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
              >
                <MaterialIcon name="add" className="h-3.5 w-3.5" aria-hidden="true" />
                <span>New Chat</span>
              </button>
            )}
          </div>

          {/* Conversation Stream */}
          <div
            ref={chatScrollContainerRef}
            tabIndex={0}
            role="region"
            aria-label="Conversation message history"
            className="relative z-10 flex-1 overflow-y-auto px-4 sm:px-6 py-4 space-y-4 focus:outline-none"
          >
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center px-4 py-6 max-w-xl mx-auto my-auto animate-in fade-in duration-300">
                <div className="relative mb-4 flex items-center justify-center">
                  <div className="absolute h-20 w-20 rounded-full bg-emerald-100/70 animate-pulse" />
                  <div className="absolute h-16 w-16 rounded-full bg-emerald-200/50" />
                  <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-950 text-emerald-300 shadow-sm ring-4 ring-emerald-500/20">
                    <MaterialIcon name="smart_toy" className="h-6 w-6" aria-hidden="true" />
                  </div>
                </div>

                <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
                  Hey, <span className="text-emerald-800">how can I help</span> with your store today?
                </h3>
                <p className="mt-1.5 text-xs sm:text-sm text-slate-600 max-w-md leading-relaxed">
                  Ask operational retail questions powered by the FastAPI backend assistant service.
                </p>

                {/* Live Telemetry Status Pill */}
                {backendSummary ? (
                  <div className="mt-5 inline-flex flex-wrap items-center justify-center gap-2 sm:gap-3 rounded-full border border-[#e2e4de] bg-[#fafaf8] px-4 py-1.5 text-xs text-slate-700 shadow-2xs">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <MaterialIcon name="groups" className="h-3.5 w-3.5 text-emerald-700 shrink-0" aria-hidden="true" />
                      <span className="text-slate-500 font-medium">Footfall:</span>
                      <span className="font-bold text-slate-900 tabular-nums">
                        {backendSummary.todayCustomers.toLocaleString()}
                      </span>
                    </div>

                    <span className="text-slate-300 font-light select-none hidden sm:inline">·</span>

                    <div className="flex items-center gap-1.5 min-w-0">
                      <MaterialIcon name="inventory_2" className="h-3.5 w-3.5 text-rose-700 shrink-0" aria-hidden="true" />
                      <span className="text-slate-500 font-medium">Critical Shelves:</span>
                      <span className="font-bold text-rose-800 tabular-nums">
                        {backendSummary.criticalShelvesCount}
                      </span>
                    </div>

                    <span className="text-slate-300 font-light select-none hidden sm:inline">·</span>

                    <div className="flex items-center gap-1.5 min-w-0">
                      <MaterialIcon name="schedule" className="h-3.5 w-3.5 text-amber-700 shrink-0" aria-hidden="true" />
                      <span className="text-slate-500 font-medium">Longest Queue:</span>
                      <span className="font-bold text-slate-900 truncate">
                        {backendSummary.longestQueueCheckout} ({backendSummary.longestQueueCount})
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-[#e2e4de] bg-[#fafaf8] px-4 py-1.5 text-xs text-slate-500 shadow-2xs">
                    <span className="h-2 w-2 rounded-full bg-amber-500" />
                    <span>Awaiting backend connection at http://localhost:8000</span>
                  </div>
                )}
              </div>
            ) : (
              messages.map((message) => {
                const isAssistant = message.sender === "assistant";
                return (
                  <div
                    key={message.id}
                    className={`flex items-start gap-2.5 ${
                      isAssistant ? "justify-start" : "justify-end"
                    }`}
                  >
                    {isAssistant && (
                      <div
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg shadow-2xs mt-0.5 ${
                          message.isError
                            ? "bg-rose-900 text-rose-200"
                            : "bg-emerald-950 text-emerald-300"
                        }`}
                      >
                        <MaterialIcon
                          name={message.isError ? "error" : "smart_toy"}
                          className="h-3.5 w-3.5"
                          aria-hidden="true"
                        />
                      </div>
                    )}

                    <div
                      className={`rounded-2xl text-xs leading-relaxed ${
                        isAssistant
                          ? message.isError
                            ? "bg-rose-50 text-rose-950 border border-rose-200 rounded-tl-xs px-4 sm:px-5 py-3.5 max-w-[88%] shadow-2xs"
                            : "bg-[#fafaf8] text-slate-900 border border-[#eeefec] rounded-tl-xs px-4 sm:px-5 py-3.5 max-w-[88%] shadow-2xs"
                          : "bg-emerald-900 text-white font-medium rounded-tr-xs px-4 py-2.5 max-w-[80%] shadow-2xs"
                      }`}
                    >
                      {/* Bubble Header for Assistant */}
                      {isAssistant && (
                        <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-[#eeefec]/80 text-[10px]">
                          <span
                            className={`font-bold tracking-wide uppercase ${
                              message.isError ? "text-rose-800" : "text-emerald-800"
                            }`}
                          >
                            {message.isError ? "Connection Notice" : "RetailIQ Copilot"}
                          </span>
                          <span className="text-slate-500 font-mono tabular-nums">{message.time}</span>
                        </div>
                      )}

                      <div className="whitespace-pre-wrap leading-relaxed text-xs">
                        {message.text}
                      </div>

                      {/* Suggested Follow-ups */}
                      {isAssistant && message.suggestedFollowUps && message.suggestedFollowUps.length > 0 && (
                        <div className="mt-2.5 pt-2 border-t border-[#eeefec]/80 flex flex-wrap items-center gap-1.5">
                          <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                            Suggested:
                          </span>
                          {message.suggestedFollowUps.map((chip) => (
                            <button
                              key={chip}
                              type="button"
                              onClick={() => handleSend(chip)}
                              disabled={isLoading}
                              className="rounded-full border border-[#e6e7e3] bg-white px-2.5 py-0.5 text-[11px] font-medium text-slate-700 hover:border-emerald-700 hover:bg-[#fafaf8] hover:text-emerald-950 transition-colors shadow-2xs cursor-pointer"
                            >
                              {chip}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Bubble Footer & Actions */}
                      <div
                        className={`mt-2 flex items-center justify-between gap-2 flex-wrap text-[11px] ${
                          isAssistant ? "text-slate-500" : "text-emerald-100"
                        }`}
                      >
                        {isAssistant ? (
                          <>
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => copyToClipboard(message.id, message.text)}
                                className="inline-flex items-center gap-1 font-semibold text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
                                title="Copy response to clipboard"
                              >
                                {copiedId === message.id ? (
                                  <>
                                    <MaterialIcon name="check" className="h-3 w-3 text-emerald-800" aria-hidden="true" />
                                    <span className="text-emerald-800 font-bold">Copied</span>
                                  </>
                                ) : (
                                  <>
                                    <MaterialIcon name="content_copy" className="h-3 w-3 text-slate-500" aria-hidden="true" />
                                    <span>Copy</span>
                                  </>
                                )}
                              </button>
                              {message.source && (
                                <>
                                  <span className="text-slate-300">·</span>
                                  <span className="text-[10px] text-slate-500 font-medium">
                                    {message.source}
                                  </span>
                                </>
                              )}
                            </div>
                            <span className="font-mono tabular-nums text-slate-500">{message.time}</span>
                          </>
                        ) : (
                          <>
                            <span className="font-mono tabular-nums text-emerald-200">{message.time}</span>
                            <span className="text-[11px] font-semibold text-emerald-200">You (Manager)</span>
                          </>
                        )}
                      </div>
                    </div>

                    {!isAssistant && (
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-200 text-slate-800 font-bold text-[11px] shadow-2xs mt-0.5">
                        SL
                      </div>
                    )}
                  </div>
                );
              })
            )}

            {/* Loading Indicator */}
            {isLoading && (
              <div
                role="status"
                aria-live="polite"
                className="flex items-start gap-2.5"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-950 text-emerald-300 shadow-2xs mt-0.5">
                  <MaterialIcon name="smart_toy" className="h-3.5 w-3.5" aria-hidden="true" />
                </div>
                <div className="rounded-2xl rounded-tl-xs bg-[#fafaf8] border border-[#eeefec] px-4 py-2.5 text-xs shadow-2xs">
                  <div className="flex items-center gap-2 text-slate-600">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-700 animate-bounce" />
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-emerald-700 animate-bounce"
                      style={{ animationDelay: "150ms" }}
                    />
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-emerald-700 animate-bounce"
                      style={{ animationDelay: "300ms" }}
                    />
                    <span className="ml-1 text-xs font-medium text-slate-700">
                      Querying FastAPI assistant service...
                    </span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Area: Suggestion Chips + Composer */}
          <div className="relative z-10 p-3 sm:p-4 bg-white/90 backdrop-blur-xs border-t border-[#eeefec] shrink-0">
            <div className="flex flex-wrap items-center justify-center gap-2 mb-3">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt.label}
                  type="button"
                  onClick={() => handleSend(prompt.label)}
                  disabled={isLoading}
                  className="inline-flex items-center gap-1.5 rounded-full border border-[#e6e7e3] bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-emerald-700 hover:bg-[#fafaf8] hover:text-emerald-950 transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
                >
                  <MaterialIcon name={prompt.icon} className="h-3.5 w-3.5 text-emerald-800" aria-hidden="true" />
                  <span>{prompt.label}</span>
                </button>
              ))}
            </div>

            <div className="rounded-2xl border border-[#e2e4de] bg-[#fafaf8] p-2.5 sm:p-3 focus-within:bg-white focus-within:border-emerald-700 focus-within:ring-2 focus-within:ring-emerald-700/20 transition-all shadow-xs">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
                className="flex flex-col gap-2"
              >
                <textarea
                  ref={textareaRef}
                  rows={1}
                  aria-label="Ask an operational question"
                  placeholder="Ask about visitor counts, low shelf stock, queue wait times, or store alerts..."
                  value={inputMessage}
                  onChange={handleInput}
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                  className="w-full resize-none bg-transparent px-2 py-1 text-xs sm:text-sm text-slate-900 placeholder:text-slate-500 focus:outline-none min-h-[38px] max-h-[120px] leading-relaxed"
                />

                <div className="flex items-center justify-between pt-1 border-t border-[#eeefec]">
                  <div className="inline-flex items-center gap-1.5 rounded-full bg-white border border-[#e6e7e3] px-2.5 py-1 text-[11px] font-semibold text-slate-700 shadow-2xs">
                    <MaterialIcon name="api" className="h-3.5 w-3.5 text-emerald-800" aria-hidden="true" />
                    <span>POST /api/v1/assistant/chat</span>
                  </div>

                  <button
                    type="submit"
                    disabled={!inputMessage.trim() || isLoading}
                    aria-label="Send message"
                    className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                      !inputMessage.trim() || isLoading
                        ? "bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-200 shadow-none"
                        : "bg-emerald-900 text-white hover:bg-emerald-950 shadow-2xs"
                    }`}
                  >
                    {isLoading ? (
                      <>
                        <span className="h-1.5 w-1.5 rounded-full bg-white animate-ping" />
                        <span>Querying...</span>
                      </>
                    ) : (
                      <>
                        <span>Send</span>
                        <MaterialIcon name="arrow_upward" className="h-3.5 w-3.5" aria-hidden="true" />
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>

            <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500 px-1">
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-[#e6e7e3] bg-[#f2f3ef] px-1 py-0.2 font-mono text-[9px] text-slate-700">Enter</kbd>
                <span>to send</span>
                <span className="text-slate-300">·</span>
                <kbd className="rounded border border-[#e6e7e3] bg-[#f2f3ef] px-1 py-0.2 font-mono text-[9px] text-slate-700">Shift + Enter</kbd>
                <span>for new line</span>
              </span>
              <span className="text-slate-500 font-medium hidden sm:inline">
                Dispatches to FastAPI LLM Assistant endpoint
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
