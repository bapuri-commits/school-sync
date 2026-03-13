import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import type { CourseDetail as CourseDetailType } from "../types";

type Tab = "syllabus" | "grades" | "attendance" | "notices" | "assignments" | "materials";

const TABS: { key: Tab; label: string }[] = [
  { key: "syllabus", label: "강의계획서" },
  { key: "grades", label: "성적" },
  { key: "attendance", label: "출석" },
  { key: "notices", label: "공지" },
  { key: "assignments", label: "과제" },
  { key: "materials", label: "자료" },
];

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    출석: "bg-emerald-500/20 text-emerald-400",
    결석: "bg-red-500/20 text-red-400",
    지각: "bg-amber-500/20 text-amber-400",
    조퇴: "bg-amber-500/20 text-amber-400",
    유고결석: "bg-blue-500/20 text-blue-400",
    미기록: "bg-gray-500/20 text-gray-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] ?? styles["미기록"]}`}>
      {status}
    </span>
  );
}

function SyllabusTab({ data }: { data: CourseDetailType }) {
  const s = data.syllabus;
  if (!s) return <p className="text-[var(--color-text-muted)]">강의계획서 데이터 없음</p>;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ["교수", s.professor],
          ["이메일", s.email],
          ["강의실", s.classroom],
        ].map(([label, val]) => (
          <div key={label} className="bg-[var(--color-bg)] rounded p-3">
            <p className="text-xs text-[var(--color-text-muted)]">{label}</p>
            <p className="text-sm mt-0.5">{val || "-"}</p>
          </div>
        ))}
      </div>
      {s.overview && (
        <div>
          <h4 className="text-xs text-[var(--color-text-muted)] mb-1">개요</h4>
          <p className="text-sm leading-relaxed">{s.overview}</p>
        </div>
      )}
      {s.textbooks?.length > 0 && (
        <div>
          <h4 className="text-xs text-[var(--color-text-muted)] mb-1">교재</h4>
          <ul className="text-sm space-y-1">
            {s.textbooks.map((t, i) => (
              <li key={i}>
                <span className="text-[var(--color-text-muted)]">[{t.type}]</span> {t.title}
              </li>
            ))}
          </ul>
        </div>
      )}
      {s.weekly_plan?.length > 0 && (
        <div>
          <h4 className="text-xs text-[var(--color-text-muted)] mb-2">주차별 계획</h4>
          <div className="grid gap-1">
            {s.weekly_plan.map((w) => (
              <div key={w.week} className="flex gap-3 text-sm py-1">
                <span className="text-[var(--color-text-muted)] w-10 shrink-0">{w.week}주</span>
                <span className="whitespace-pre-line">{w.topic}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GradesTab({ data }: { data: CourseDetailType }) {
  if (!data.grades.length)
    return <p className="text-[var(--color-text-muted)]">성적 데이터 없음</p>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
          <th className="py-2 font-medium">항목</th>
          <th className="py-2 font-medium">카테고리</th>
          <th className="py-2 font-medium text-right">점수</th>
          <th className="py-2 font-medium text-right">비중</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-[var(--color-border)]">
        {data.grades.map((g, i) => (
          <tr key={i}>
            <td className="py-2">{g.item_name}</td>
            <td className="py-2 text-[var(--color-text-muted)]">{g.category}</td>
            <td className="py-2 text-right font-mono">{g.score}</td>
            <td className="py-2 text-right text-[var(--color-text-muted)]">{g.weight}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AttendanceTab({ data }: { data: CourseDetailType }) {
  if (!data.attendance.length)
    return <p className="text-[var(--color-text-muted)]">출석 데이터 없음</p>;

  const weeks = [...new Set(data.attendance.map((a) => a.week))].sort((a, b) => a - b);

  return (
    <div className="space-y-1">
      {weeks.map((w) => {
        const records = data.attendance.filter((a) => a.week === w);
        const hasIssue = records.some((r) => ["결석", "지각", "조퇴"].includes(r.status));
        return (
          <div
            key={w}
            className={`flex items-center gap-3 text-sm py-1.5 px-2 rounded ${hasIssue ? "bg-red-500/5" : ""}`}
          >
            <span className="text-[var(--color-text-muted)] w-10 shrink-0">{w}주</span>
            <span className="text-[var(--color-text-muted)] w-24 shrink-0">{records[0]?.date}</span>
            <div className="flex gap-1.5 flex-wrap">
              {records.map((r, i) => (
                <StatusBadge key={i} status={r.status} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function NoticesTab({ data }: { data: CourseDetailType }) {
  if (!data.notices.length)
    return <p className="text-[var(--color-text-muted)]">공지 없음</p>;
  return (
    <ul className="divide-y divide-[var(--color-border)]">
      {data.notices.map((n, i) => (
        <li key={i} className="py-3">
          <div className="flex items-start gap-3">
            <span className="text-xs text-[var(--color-text-muted)] shrink-0 w-20">{n.date}</span>
            <div className="flex-1 min-w-0">
              <a
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm hover:text-[var(--color-primary)] transition-colors"
              >
                {n.title}
              </a>
              <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
                {n.board_name} · {n.author}
              </p>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function AssignmentsTab({ data }: { data: CourseDetailType }) {
  const items = [...data.assignments, ...data.deadlines.map((d) => ({
    title: d.title,
    activity_type: "deadline",
    url: d.url,
    _dday: d.d_day,
  }))];

  if (!items.length)
    return <p className="text-[var(--color-text-muted)]">과제/활동 없음</p>;

  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-center gap-3 text-sm py-2 border-b border-[var(--color-border)]">
          <span className="px-2 py-0.5 rounded bg-[var(--color-surface-hover)] text-xs text-[var(--color-text-muted)]">
            {item.activity_type}
          </span>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 hover:text-[var(--color-primary)] transition-colors"
          >
            {item.title}
          </a>
          {"_dday" in item && typeof item._dday === "number" && (
            <span className={`text-xs ${item._dday <= 3 ? "text-red-400" : "text-[var(--color-text-muted)]"}`}>
              D-{item._dday}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function MaterialsTab({ data }: { data: CourseDetailType }) {
  if (!data.materials.length)
    return <p className="text-[var(--color-text-muted)]">다운로드된 자료 없음</p>;
  return (
    <ul className="space-y-2">
      {data.materials.map((m, i) => (
        <li key={i} className="flex items-center gap-3 text-sm py-2 border-b border-[var(--color-border)]">
          <span className="text-[var(--color-primary)]">
            {m.filename.endsWith(".pdf") ? "PDF" : m.filename.endsWith(".pptx") ? "PPT" : "FILE"}
          </span>
          <span className="flex-1">{m.filename}</span>
          <span className="text-[var(--color-text-muted)] text-xs">
            {m.size_kb > 1024 ? `${(m.size_kb / 1024).toFixed(1)}MB` : `${m.size_kb}KB`}
          </span>
        </li>
      ))}
    </ul>
  );
}

const TAB_COMPONENTS: Record<Tab, React.FC<{ data: CourseDetailType }>> = {
  syllabus: SyllabusTab,
  grades: GradesTab,
  attendance: AttendanceTab,
  notices: NoticesTab,
  assignments: AssignmentsTab,
  materials: MaterialsTab,
};

export default function CourseDetail() {
  const { name } = useParams<{ name: string }>();
  const [data, setData] = useState<CourseDetailType | null>(null);
  const [tab, setTab] = useState<Tab>("syllabus");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!name) return;
    setLoading(true);
    setError(null);
    api.course(decodeURIComponent(name))
      .then((d) => setData(d))
      .catch((e) => setError(e.message ?? "API 연결 실패"))
      .finally(() => setLoading(false));
  }, [name]);

  if (loading)
    return <div className="text-[var(--color-text-muted)] py-12 text-center">불러오는 중...</div>;

  if (error || !data)
    return (
      <div className="py-12 text-center">
        <Link to="/" className="text-sm text-[var(--color-text-muted)] hover:text-white">← 대시보드</Link>
        <p className="text-red-400 font-semibold mt-4">과목 데이터 로드 실패</p>
        <p className="text-[var(--color-text-muted)] text-sm mt-1">{error}</p>
      </div>
    );

  const TabContent = TAB_COMPONENTS[tab];

  return (
    <div className="space-y-4">
      {/* Breadcrumb + Title */}
      <div>
        <Link to="/" className="text-sm text-[var(--color-text-muted)] hover:text-white transition-colors">
          ← 대시보드
        </Link>
        <h1 className="text-xl font-bold mt-1">{data.short_name}</h1>
        <p className="text-sm text-[var(--color-text-muted)]">{data.professor} · {data.name}</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--color-border)] pb-0">
        {TABS.map((t) => {
          const count =
            t.key === "grades" ? data.grades.length :
            t.key === "notices" ? data.notices.length :
            t.key === "materials" ? data.materials.length : null;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-2 text-sm rounded-t-md transition-colors ${
                tab === t.key
                  ? "bg-[var(--color-surface)] text-white border border-[var(--color-border)] border-b-transparent -mb-px"
                  : "text-[var(--color-text-muted)] hover:text-white"
              }`}
            >
              {t.label}
              {count !== null && count > 0 && (
                <span className="ml-1.5 text-xs text-[var(--color-text-muted)]">{count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
        <TabContent data={data} />
      </div>
    </div>
  );
}
