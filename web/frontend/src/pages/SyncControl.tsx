import { useEffect, useRef, useState } from "react";

interface TaskStatus {
  status: "idle" | "running" | "completed" | "failed";
  task_type: string;
  started_at: string;
  finished_at: string;
  exit_code: number | null;
  log_lines: number;
}

type SSEChunk =
  | { type: "log"; text: string }
  | { type: "status"; status: string; exit_code: number | null }
  | { type: "done" };

interface AutoSyncStatus {
  enabled: boolean;
  interval_hours: number;
  last_auto: string | null;
  next_auto: string | null;
}

export default function SyncControl() {
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [lastRun, setLastRun] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [autoSync, setAutoSync] = useState<AutoSyncStatus | null>(null);

  const [crawlSites, setCrawlSites] = useState<Set<string>>(new Set(["eclass"]));
  const [crawlDownload, setCrawlDownload] = useState(false);
  const [packCourse, setPackCourse] = useState("");

  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchAutoSync = async () => {
    try {
      const r = await fetch("/api/sync/auto-status");
      if (r.ok) setAutoSync(await r.json());
    } catch { /* ignore */ }
  };

  const toggleAutoSync = async () => {
    if (!autoSync) return;
    try {
      const r = await fetch("/api/sync/auto-toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !autoSync.enabled }),
      });
      if (r.ok) fetchAutoSync();
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchStatus();
    fetchLastRun();
    fetchAutoSync();
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const fetchStatus = async () => {
    try {
      const r = await fetch("/api/sync/status");
      const data = await r.json();
      setTaskStatus(data);
      if (data.status === "running") startLogStream();
    } catch { /* ignore */ }
  };

  const fetchLastRun = async () => {
    try {
      const r = await fetch("/api/sync/last-run");
      const data = await r.json();
      setLastRun(data.last_run ? new Date(data.last_run).toLocaleString("ko-KR") : null);
    } catch { /* ignore */ }
  };

  const startLogStream = async () => {
    setStreaming(true);
    const pending: string[] = [];
    let flushTimer: ReturnType<typeof setInterval> | null = null;

    const flush = () => {
      if (pending.length > 0) {
        const batch = pending.splice(0);
        setLogs((prev) => [...prev, ...batch]);
      }
    };
    flushTimer = setInterval(flush, 200);

    try {
      const res = await fetch("/api/sync/logs/stream");
      if (!res.body) { setStreaming(false); return; }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop()!;
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const chunk: SSEChunk = JSON.parse(line.slice(6));
            if (chunk.type === "log") {
              pending.push(chunk.text);
            } else if (chunk.type === "status") {
              setTaskStatus((prev) => prev ? { ...prev, status: chunk.status as TaskStatus["status"], exit_code: chunk.exit_code } : prev);
            }
          } catch { /* skip */ }
        }
      }
    } catch { /* ignore */ }
    finally {
      if (flushTimer) clearInterval(flushTimer);
      flush();
    }
    setStreaming(false);
    fetchStatus();
    fetchLastRun();
  };

  const triggerAction = async (endpoint: string, body: object) => {
    setLogs([]);
    try {
      const r = await fetch(`/api/sync/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (data.error) {
        setLogs([`[오류] ${data.error}`]);
        return;
      }
      fetchStatus();
      await new Promise((r) => setTimeout(r, 300));
      startLogStream();
    } catch (e) {
      setLogs([`[연결 오류] ${e instanceof Error ? e.message : "unknown"}`]);
    }
  };

  const toggleSite = (site: string) => {
    setCrawlSites((prev) => {
      const next = new Set(prev);
      next.has(site) ? next.delete(site) : next.add(site);
      return next;
    });
  };

  const isRunning = taskStatus?.status === "running" || streaming;
  const SITES = ["eclass", "portal", "department", "ndrims"];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <h1 className="text-xl font-bold">동기화 제어</h1>
        {lastRun && (
          <p className="text-sm text-[var(--color-text-muted)]">마지막 크롤링: {lastRun}</p>
        )}
      </div>

      {/* 자동 동기화 상태 */}
      {autoSync && (
        <section className="flex items-center justify-between bg-[var(--color-surface)] rounded-lg px-4 py-3 border border-[var(--color-border)]">
          <div className="flex items-center gap-3">
            <span className={`inline-block w-2 h-2 rounded-full ${autoSync.enabled ? "bg-emerald-400" : "bg-[var(--color-text-muted)]"}`} />
            <div>
              <span className="text-sm font-medium">자동 동기화</span>
              <span className="text-xs text-[var(--color-text-muted)] ml-2">
                {autoSync.enabled ? `${autoSync.interval_hours}시간 간격` : "비활성"}
                {autoSync.enabled && autoSync.next_auto && ` · 다음: ${new Date(autoSync.next_auto).toLocaleString("ko-KR")}`}
                {autoSync.last_auto && ` · 마지막: ${new Date(autoSync.last_auto).toLocaleString("ko-KR")}`}
              </span>
            </div>
          </div>
          <button
            onClick={toggleAutoSync}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              autoSync.enabled
                ? "bg-[var(--color-text-muted)]/20 text-[var(--color-text-muted)] hover:bg-red-500/20 hover:text-red-400"
                : "bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30"
            }`}
          >
            {autoSync.enabled ? "끄기" : "켜기"}
          </button>
        </section>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 크롤링 패널 */}
        <section className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <h2 className="text-sm font-semibold mb-3">크롤링</h2>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {SITES.map((s) => (
                <button
                  key={s}
                  onClick={() => toggleSite(s)}
                  disabled={isRunning}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    crawlSites.has(s)
                      ? "border-[var(--color-primary)] bg-[var(--color-primary)]/20 text-[var(--color-primary)]"
                      : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]"
                  } disabled:opacity-50`}
                >
                  {s}
                </button>
              ))}
              {crawlSites.has("ndrims") && (
                <span className="text-[10px] text-amber-400 ml-1">SSO 수동 로그인 필요</span>
              )}
            </div>
            <label className="flex items-center gap-1.5 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={crawlDownload}
                onChange={(e) => setCrawlDownload(e.target.checked)}
                disabled={isRunning}
              />
              <span className="text-[var(--color-text-muted)]">자료 다운로드 포함</span>
            </label>
            <button
              onClick={() => triggerAction("crawl", { sites: [...crawlSites], download: crawlDownload })}
              disabled={isRunning || crawlSites.size === 0}
              className="w-full py-2 bg-[var(--color-primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--color-primary-dark)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isRunning && taskStatus?.task_type === "crawl" ? "크롤링 중..." : "크롤링 시작"}
            </button>
          </div>
        </section>

        {/* 정규화 패널 */}
        <section className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <h2 className="text-sm font-semibold mb-3">정규화</h2>
          <p className="text-xs text-[var(--color-text-muted)] mb-3">
            기존 raw 데이터를 정규화하고 학습 컨텍스트를 재생성합니다.
          </p>
          <button
            onClick={() => triggerAction("normalize", {})}
            disabled={isRunning}
            className="w-full py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning && taskStatus?.task_type === "normalize" ? "정규화 중..." : "정규화 실행"}
          </button>
        </section>

        {/* 패키징 패널 */}
        <section className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <h2 className="text-sm font-semibold mb-3">패키징 (lesson-assist)</h2>
          <div className="space-y-3">
            <input
              type="text"
              value={packCourse}
              onChange={(e) => setPackCourse(e.target.value)}
              placeholder="과목명 (빈칸 = 전체)"
              disabled={isRunning}
              className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50 placeholder:text-[var(--color-text-muted)]"
            />
            <button
              onClick={() =>
                triggerAction("pack", packCourse ? { course: packCourse } : { all_courses: true })
              }
              disabled={isRunning}
              className="w-full py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isRunning && taskStatus?.task_type === "pack" ? "패키징 중..." : "패키징 시작"}
            </button>
          </div>
        </section>
      </div>

      {/* 상태 바 */}
      {taskStatus && taskStatus.status !== "idle" && taskStatus.task_type && (
        <div
          className={`flex items-center gap-3 px-4 py-2 rounded-lg border text-sm ${
            taskStatus.status === "running"
              ? "border-blue-500/30 bg-blue-500/10 text-blue-400"
              : taskStatus.status === "completed"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-red-500/30 bg-red-500/10 text-red-400"
          }`}
        >
          <span className="font-medium">
            {taskStatus.status === "running" && "실행 중"}
            {taskStatus.status === "completed" && "완료"}
            {taskStatus.status === "failed" && "실패"}
          </span>
          <span className="text-xs opacity-75">
            {taskStatus.task_type} · 시작: {taskStatus.started_at}
            {taskStatus.finished_at && ` · 종료: ${taskStatus.finished_at}`}
            {taskStatus.exit_code !== null && ` · exit=${taskStatus.exit_code}`}
          </span>
        </div>
      )}

      {/* 로그 */}
      {logs.length > 0 && (
        <section className="bg-[var(--color-bg)] rounded-lg border border-[var(--color-border)] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-[var(--color-surface)] border-b border-[var(--color-border)]">
            <h2 className="text-xs font-semibold text-[var(--color-text-muted)]">실행 로그</h2>
            <span className="text-xs text-[var(--color-text-muted)]">{logs.length}줄</span>
          </div>
          <div className="p-4 max-h-80 overflow-y-auto font-mono text-xs leading-relaxed">
            {logs.map((line, i) => (
              <div key={i} className={line.startsWith("[StudyHub]") ? "text-[var(--color-primary)]" : "text-[var(--color-text-muted)]"}>
                {line || "\u00A0"}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </section>
      )}
    </div>
  );
}
