import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Course, DashboardData, Notice } from "../types";

function DdayBadge({ dDay }: { dDay: number }) {
  const color =
    dDay <= 1
      ? "bg-red-500/20 text-red-400"
      : dDay <= 3
        ? "bg-amber-500/20 text-amber-400"
        : "bg-blue-500/20 text-blue-400";
  const label = dDay === 0 ? "D-Day" : dDay < 0 ? `D+${-dDay}` : `D-${dDay}`;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${color}`}>
      {label}
    </span>
  );
}

function NewBadge() {
  return <span className="inline-block w-2 h-2 rounded-full bg-blue-400 animate-pulse" />;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.dashboard(), api.courses()])
      .then(([d, c]) => {
        setData(d);
        setCourses(c);
      })
      .catch((e) => setError(e.message ?? "API 연결 실패"))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return <div className="text-[var(--color-text-muted)] py-12 text-center">불러오는 중...</div>;

  if (error || !data)
    return (
      <div className="py-12 text-center">
        <p className="text-red-400 font-semibold">데이터 로드 실패</p>
        <p className="text-[var(--color-text-muted)] text-sm mt-1">{error ?? "알 수 없는 오류"}</p>
        <p className="text-[var(--color-text-muted)] text-xs mt-3">백엔드 서버가 실행 중인지 확인하세요 (포트 8000)</p>
      </div>
    );

  const lastCrawl = data.last_run?.last_run
    ? new Date(data.last_run.last_run).toLocaleString("ko-KR")
    : "기록 없음";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            {data.today} ({data.weekday})
          </h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            마지막 동기화: {lastCrawl}
          </p>
        </div>
      </div>

      {/* Top row: 시간표 + 마감 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 오늘 시간표 */}
        <section className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <h2 className="text-sm font-semibold text-[var(--color-text-muted)] mb-3">
            오늘 수업
          </h2>
          {data.today_classes.length === 0 ? (
            <p className="text-[var(--color-text-muted)] text-sm">오늘은 수업이 없습니다</p>
          ) : (
            <ul className="space-y-2">
              {data.today_classes.map((c, i) => (
                <li key={i} className="flex justify-between text-sm">
                  <span className="font-medium">{c.course_name}</span>
                  <span className="text-[var(--color-text-muted)]">
                    {c.schedule} {c.room && `· ${c.room}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 마감 임박 */}
        <section className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <h2 className="text-sm font-semibold text-[var(--color-text-muted)] mb-3">
            마감 임박
          </h2>
          {data.upcoming_deadlines.length === 0 ? (
            <p className="text-[var(--color-text-muted)] text-sm">임박한 마감이 없습니다</p>
          ) : (
            <ul className="space-y-2">
              {data.upcoming_deadlines.map((d, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <DdayBadge dDay={d.d_day} />
                  <span className="flex-1 truncate">{d.title}</span>
                  <span className="text-[var(--color-text-muted)] text-xs shrink-0">
                    {d.course_name}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* 과목 카드 */}
      <section>
        <h2 className="text-sm font-semibold text-[var(--color-text-muted)] mb-3">
          수강 과목
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {courses.map((c) => {
            const hasNewNotice = data.new_notice_courses.includes(c.short_name);
            return (
              <Link
                key={c.id}
                to={`/courses/${encodeURIComponent(c.short_name)}`}
                className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)] hover:border-[var(--color-primary)] transition-colors group"
              >
                <div className="flex items-start justify-between">
                  <h3 className="font-semibold text-sm group-hover:text-[var(--color-primary)] transition-colors">
                    {c.short_name}
                  </h3>
                  {hasNewNotice && <NewBadge />}
                </div>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                  {c.professor}
                </p>
              </Link>
            );
          })}
        </div>
      </section>

      {/* 최근 공지 */}
      <NoticeSection
        eclassNotices={data.recent_eclass_notices}
        otherNotices={data.recent_other_notices}
      />
    </div>
  );
}

function NoticeSection({ eclassNotices, otherNotices }: { eclassNotices: Notice[]; otherNotices: Notice[] }) {
  const [tab, setTab] = useState<"eclass" | "other">("eclass");
  const [expanded, setExpanded] = useState<number | null>(null);
  const items = tab === "eclass" ? eclassNotices : otherNotices;

  return (
    <section className="bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
      <div className="flex items-center justify-between px-4 pt-3 pb-2">
        <div className="flex gap-2">
          {(["eclass", "other"] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setExpanded(null); }}
              className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                tab === t
                  ? "border-[var(--color-primary)] bg-[var(--color-primary)]/20 text-[var(--color-primary)]"
                  : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]"
              }`}
            >
              {t === "eclass" ? `eClass (${eclassNotices.length})` : `학교 공지 (${otherNotices.length})`}
            </button>
          ))}
        </div>
        <Link to="/notices" className="text-xs text-[var(--color-primary)] hover:underline">전체 보기</Link>
      </div>
      <ul className="divide-y divide-[var(--color-border)] px-4 pb-3">
        {items.length === 0 ? (
          <li className="py-3 text-sm text-[var(--color-text-muted)]">공지가 없습니다</li>
        ) : items.map((n, i) => (
          <li key={i} className="py-2">
            <div
              className="flex items-start gap-3 text-sm cursor-pointer hover:text-[var(--color-primary)] transition-colors"
              onClick={() => setExpanded(expanded === i ? null : i)}
            >
              <span className="text-[var(--color-text-muted)] text-xs shrink-0 w-20">{n.date}</span>
              {tab === "eclass" && n.course_name && (
                <span className="px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-xs text-[var(--color-text-muted)] shrink-0">
                  {n.course_name}
                </span>
              )}
              <span className="flex-1 truncate">{n.title}</span>
              {tab === "eclass" && n.body && (
                <span className="text-[var(--color-text-muted)] text-xs shrink-0">
                  {expanded === i ? "접기" : "펼치기"}
                </span>
              )}
            </div>
            {expanded === i && tab === "eclass" && n.body && (
              <div className="mt-2 ml-24 text-xs text-[var(--color-text-muted)] whitespace-pre-wrap bg-[var(--color-bg)] rounded p-3 border border-[var(--color-border)]">
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
              <div className="mt-2 ml-24 text-xs text-[var(--color-text-muted)]">
                본문 없음 —{" "}
                <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-primary)] hover:underline">
                  eClass에서 보기
                </a>
              </div>
            )}
            {expanded === i && tab === "other" && (
              <div className="mt-2 ml-24 text-xs text-[var(--color-text-muted)]">
                <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-primary)] hover:underline">
                  원본 링크에서 보기
                </a>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
