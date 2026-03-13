import { useEffect, useRef, useState } from "react";
import { api } from "../api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function AskChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [webSearch, setWebSearch] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || streaming) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setStreaming(true);

    let assistantText = "";
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      for await (const chunk of api.askStream(q, webSearch)) {
        if (chunk.type === "text") {
          assistantText += chunk.text;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "assistant", content: assistantText };
            return updated;
          });
        } else if (chunk.type === "error") {
          assistantText = `[오류] ${chunk.text}`;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "assistant", content: assistantText };
            return updated;
          });
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: `[연결 오류] ${err instanceof Error ? err.message : "알 수 없는 오류"}`,
        };
        return updated;
      });
    }

    setStreaming(false);
    inputRef.current?.focus();
  };

  const handleReset = async () => {
    await api.askReset();
    setMessages([]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-lg font-bold">AI Q&A</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={webSearch}
              onChange={(e) => setWebSearch(e.target.checked)}
              className="rounded"
            />
            <span className="text-[var(--color-text-muted)]">웹검색</span>
          </label>
          <button
            onClick={handleReset}
            className="text-xs px-2 py-1 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-white transition-colors"
          >
            대화 초기화
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-[var(--color-text-muted)]">
              <p className="text-lg mb-2">학교 데이터 기반 AI 질의</p>
              <p className="text-sm">과제, 시간표, 성적, 출석 등 무엇이든 물어보세요</p>
              <div className="mt-4 flex flex-wrap gap-2 justify-center">
                {["이번주 과제 뭐 있어?", "오늘 수업 몇 시야?", "내 출석 현황 알려줘", "GPA 얼마야?"].map((q) => (
                  <button
                    key={q}
                    onClick={() => { setInput(q); inputRef.current?.focus(); }}
                    className="text-xs px-3 py-1.5 rounded-full border border-[var(--color-border)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-surface)] border border-[var(--color-border)]"
              }`}
            >
              {msg.content || (streaming && i === messages.length - 1 ? "..." : "")}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-2 pt-3 border-t border-[var(--color-border)]">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="질문을 입력하세요..."
          disabled={streaming}
          className="flex-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50 placeholder:text-[var(--color-text-muted)]"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="px-4 py-2.5 bg-[var(--color-primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--color-primary-dark)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {streaming ? "응답 중..." : "전송"}
        </button>
      </form>
    </div>
  );
}
