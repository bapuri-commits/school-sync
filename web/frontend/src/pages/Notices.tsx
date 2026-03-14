import { useEffect, useState } from "react";
import { api } from "../api";
import type { Notice } from "../types";

export default function Notices() {
  const [notices, setNotices] = useState<Notice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"eclass" | "other">("eclass");
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    api.notices()
      .then(setNotices)
      .catch((e) => setError(e.message ?? "공지 로드 실패"))
      .finally(() => setLoading(false));
  }, []);

  const eclass = notices.filter((n) => n.source_site === "eclass");
  const other = notices.filter((n) => n.source_site !== "eclass");
  const items = tab === "eclass" ? eclass : other;

  if (loading) return <div className="text-[var(--color-text-muted)] py-12 text-center">불러오는 중...</div>;
  if (error) return <div className="py-12 text-center"><p className="text-red-400">{error}</p></div>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">공지사항</h1>

      <div className="flex gap-2">
        {(["eclass", "other"] as const).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setExpanded(null); }}
            className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
              tab === t
                ? "border-[var(--color-primary)] bg-[var(--color-primary)]/20 text-[var(--color-primary)]"
                : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]"
            }`}
          >
            {t === "eclass" ? `eClass (${eclass.length})` : `학교 공지 (${other.length})`}
          </button>
        ))}
      </div>

      <section className="bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
        <ul className="divide-y divide-[var(--color-border)]">
          {items.length === 0 ? (
            <li className="p-4 text-sm text-[var(--color-text-muted)]">공지가 없습니다</li>
          ) : items.map((n, i) => (
            <li key={i} className="px-4 py-3">
              <div
                className="flex items-start gap-3 text-sm cursor-pointer hover:text-[var(--color-primary)] transition-colors"
                onClick={() => setExpanded(expanded === i ? null : i)}
              >
                <span className="text-[var(--color-text-muted)] text-xs shrink-0 w-24">{n.date}</span>
                {tab === "eclass" && n.course_name && (
                  <span className="px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-xs text-[var(--color-text-muted)] shrink-0">
                    {n.course_name}
                  </span>
                )}
                {tab === "other" && n.board_name && (
                  <span className="px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-xs text-[var(--color-text-muted)] shrink-0">
                    {n.board_name}
                  </span>
                )}
                <span className="flex-1">{n.title}</span>
                {tab === "eclass" && n.body && (
                  <span className="text-[var(--color-text-muted)] text-xs shrink-0">
                    {expanded === i ? "접기" : "펼치기"}
                  </span>
                )}
              </div>

              {expanded === i && tab === "eclass" && n.body && (
                <div className="mt-2 ml-28 text-xs text-[var(--color-text-muted)] whitespace-pre-wrap bg-[var(--color-bg)] rounded p-3 border border-[var(--color-border)]">
                  {n.body}
                  {n.attachments && n.attachments.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
                      <span className="font-medium">첨부: </span>
                      {n.attachments.map((a, j) => (
                        <a key={j} href={a.url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-primary)] hover:underline mr-2">
                          {a.name}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {expanded === i && tab === "eclass" && !n.body && (
                <div className="mt-2 ml-28 text-xs text-[var(--color-text-muted)]">
                  본문 없음 —{" "}
                  <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-primary)] hover:underline">
                    eClass에서 보기
                  </a>
                </div>
              )}
              {expanded === i && tab === "other" && (
                <div className="mt-2 ml-28 text-xs text-[var(--color-text-muted)]">
                  <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-primary)] hover:underline">
                    원본 링크에서 보기
                  </a>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
