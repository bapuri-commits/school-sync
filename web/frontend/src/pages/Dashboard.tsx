import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Course, DashboardData } from "../types";

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

function StatusDot({ status }: { status: string }) {
  const color =
    status === "결석"
      ? "bg-red-400"
      : status === "지각" || status === "조퇴"
        ? "bg-amber-400"
        : "bg-emerald-400";
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
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
            const hasAttentionFlag = data.attendance_attention.includes(c.short_name);
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
                  {hasAttentionFlag && <StatusDot status="결석" />}
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
      <section className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
        <h2 className="text-sm font-semibold text-[var(--color-text-muted)] mb-3">
          최근 공지
        </h2>
        <ul className="divide-y divide-[var(--color-border)]">
          {data.recent_notices.slice(0, 8).map((n, i) => (
            <li key={i} className="py-2 flex items-start gap-3 text-sm">
              <span className="text-[var(--color-text-muted)] text-xs shrink-0 w-20">
                {n.date}
              </span>
              <span className="px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-xs text-[var(--color-text-muted)] shrink-0">
                {n.course_name}
              </span>
              <a
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 truncate hover:text-[var(--color-primary)] transition-colors"
              >
                {n.title}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
