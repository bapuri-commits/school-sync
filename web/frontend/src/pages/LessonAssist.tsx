import { useCallback, useEffect, useRef, useState } from "react";

interface DagloFile {
  filename: string;
  size: number;
  date: string | null;
}

interface DagloCourse {
  course: string;
  files: DagloFile[];
}

interface PackageFile {
  filename: string;
  size: number;
  changed?: boolean | null;
}

interface PackageCourse {
  course: string;
  files: PackageFile[];
}

interface TaskStatus {
  status: "idle" | "running" | "completed" | "failed";
  task_type: string;
  started_at: string;
  finished_at: string;
  exit_code: number | null;
}

interface CourseInfo {
  materials: { filename: string; size_kb: number }[];
  hasContext: boolean;
  lastCrawl: string | null;
}

type SSEChunk =
  | { type: "log"; text: string }
  | { type: "status"; status: string; exit_code: number | null }
  | { type: "done" };

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const MAX_CLIENT_SIZE = 50 * 1024 * 1024;
const ALLOWED_EXT = [".srt", ".txt"];

export default function LessonAssist() {
  const [courseList, setCourseList] = useState<string[]>([]);
  const [dagloFiles, setDagloFiles] = useState<DagloCourse[]>([]);
  const [packages, setPackages] = useState<PackageCourse[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadCourse, setUploadCourse] = useState("auto");
  const [uploadDate, setUploadDate] = useState("");
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [courseInfo, setCourseInfo] = useState<CourseInfo | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [gdriveEnabled, setGdriveEnabled] = useState(false);
  const [uploadingToDrive, setUploadingToDrive] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchCourses = useCallback(async () => {
    try {
      const r = await fetch("/api/la/courses");
      if (r.ok) {
        const data = await r.json();
        const list: string[] = data.courses || [];
        setCourseList(list);
        setFetchError(null);
      } else if (r.status === 401) {
        setFetchError("인증이 필요합니다");
      }
    } catch {
      setFetchError("서버에 연결할 수 없습니다");
    }
  }, []);

  const fetchFiles = useCallback(async () => {
    try {
      const r = await fetch("/api/la/files");
      if (r.ok) setDagloFiles((await r.json()).courses || []);
    } catch { /* ignore — fetchCourses handles connection errors */ }
  }, []);

  const fetchPackages = useCallback(async () => {
    try {
      const r = await fetch("/api/la/packages");
      if (r.ok) setPackages((await r.json()).packages || []);
    } catch { /* ignore */ }
  }, []);

  const fetchCourseInfo = useCallback(async (course: string) => {
    if (!course || course === "auto") { setCourseInfo(null); return; }
    try {
      const [courseRes, ctxRes, runRes] = await Promise.all([
        fetch(`/api/courses/${encodeURIComponent(course)}`),
        fetch(`/api/courses/${encodeURIComponent(course)}/context`),
        fetch("/api/sync/last-run"),
      ]);
      const materials = courseRes.ok ? (await courseRes.json()).materials || [] : [];
      const hasContext = ctxRes.ok && ctxRes.status === 200;
      const runData = runRes.ok ? await runRes.json() : {};
      setCourseInfo({ materials, hasContext, lastCrawl: runData.last_run || null });
    } catch {
      setCourseInfo({ materials: [], hasContext: false, lastCrawl: null });
    }
  }, []);

  useEffect(() => {
    fetchCourses();
    fetchFiles();
    fetchPackages();
    const checkStatus = async () => {
      try {
        const r = await fetch("/api/sync/status");
        if (r.ok) {
          const data = await r.json();
          setTaskStatus(data);
          if (data.status === "running") startLogStream();
        }
      } catch { /* ignore */ }
    };
    checkStatus();
    fetch("/api/gdrive/status").then(r => r.ok ? r.json() : null).then(d => {
      if (d) setGdriveEnabled(d.enabled);
    }).catch(() => {});
    return () => { abortRef.current?.abort(); };
  }, [fetchCourses, fetchFiles, fetchPackages]);

  useEffect(() => {
    if (uploadCourse) fetchCourseInfo(uploadCourse);
  }, [uploadCourse, fetchCourseInfo]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    setUploading(true);
    try {
      for (const file of Array.from(fileList)) {
        const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
        if (!ALLOWED_EXT.includes(ext)) {
          alert(`${file.name}: SRT 또는 TXT 파일만 가능합니다`);
          continue;
        }
        if (file.size > MAX_CLIENT_SIZE) {
          alert(`${file.name}: 파일 크기 초과 (최대 50MB)`);
          continue;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("course", uploadCourse);
        if (uploadDate) formData.append("date", uploadDate);

        const r = await fetch("/api/la/upload", { method: "POST", body: formData });
        const result = await r.json();
        if (result.status === "needs_course") {
          const picked = prompt(
            `"${result.filename}" 과목을 감지할 수 없습니다.\n과목명을 입력하세요:\n(${(result.courses || []).join(", ")})`,
          );
          if (picked) {
            const retry = new FormData();
            retry.append("file", file);
            retry.append("course", picked);
            if (uploadDate) retry.append("date", uploadDate);
            const r2 = await fetch("/api/la/upload", { method: "POST", body: retry });
            if (!r2.ok) alert(`업로드 실패: HTTP ${r2.status}`);
          }
        } else if (!r.ok) {
          const msg = typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail || result);
          alert(`업로드 실패: ${msg}`);
        }
      }
      fetchFiles();
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDelete = async (course: string, filename: string) => {
    if (!confirm(`${filename} 삭제?`)) return;
    try {
      const r = await fetch(`/api/la/files/${encodeURIComponent(course)}/${encodeURIComponent(filename)}`, { method: "DELETE" });
      if (r.ok) fetchFiles();
      else alert("삭제 실패");
    } catch {
      alert("삭제 요청 실패");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const startLogStream = async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
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
      const res = await fetch("/api/sync/logs/stream", { signal: ctrl.signal });
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
              setTaskStatus((prev) =>
                prev ? { ...prev, status: chunk.status as TaskStatus["status"], exit_code: chunk.exit_code } : prev
              );
            }
          } catch { /* skip */ }
        }
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
    } finally {
      if (flushTimer) clearInterval(flushTimer);
      flush();
    }
    setStreaming(false);
    fetchPackages();
  };

  const triggerPack = async (course?: string) => {
    setLogs([]);
    try {
      const body = course ? { course } : { all_courses: true };
      const r = await fetch("/api/sync/pack", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (data.error) {
        setLogs([`[오류] ${data.error}`]);
        return;
      }
      await new Promise((r) => setTimeout(r, 300));
      startLogStream();
    } catch (e) {
      setLogs([`[연결 오류] ${e instanceof Error ? e.message : "unknown"}`]);
    }
  };

  const uploadToDrive = async (course: string) => {
    setUploadingToDrive(course);
    try {
      const r = await fetch("/api/gdrive/upload/package", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ course }),
      });
      const data = await r.json();
      if (r.ok) {
        alert(`${course}: ${data.uploaded}개 파일 Drive 업로드 완료`);
      } else {
        alert(`Drive 업로드 실패: ${data.detail || "알 수 없는 오류"}`);
      }
    } catch {
      alert("Drive 업로드 요청 실패");
    } finally {
      setUploadingToDrive(null);
    }
  };

  const downloadAll = async (course: string, files: PackageFile[]) => {
    for (const f of files) {
      const a = document.createElement("a");
      a.href = `/api/la/packages/${encodeURIComponent(course)}/${encodeURIComponent(f.filename)}`;
      a.download = f.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      await new Promise((r) => setTimeout(r, 300));
    }
  };

  const isRunning = taskStatus?.status === "running" || streaming;
  const totalFiles = dagloFiles.reduce((acc, c) => acc + c.files.length, 0);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Lesson Assist</h1>

      {fetchError && (
        <div className="px-4 py-2 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-sm">
          {fetchError}
        </div>
      )}

      {/* 파일 업로드 */}
      <section className="bg-[var(--color-surface)] rounded-lg p-5 border border-[var(--color-border)]">
        <h2 className="text-sm font-semibold mb-4">전사본 업로드</h2>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-3 mb-4 items-end">
          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">과목</label>
            <select
              value={uploadCourse}
              onChange={(e) => setUploadCourse(e.target.value)}
              className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[var(--color-primary)]"
            >
              <option value="auto">자동 감지</option>
              {courseList.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">날짜 (선택)</label>
            <input
              type="date"
              value={uploadDate}
              onChange={(e) => setUploadDate(e.target.value)}
              className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[var(--color-primary)]"
            />
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="px-4 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm font-medium hover:bg-[var(--color-primary-dark)] disabled:opacity-50 transition-colors"
          >
            {uploading ? "업로드 중..." : "파일 선택"}
          </button>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
            dragOver
              ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10"
              : "border-[var(--color-border)] hover:border-[var(--color-primary)]/50"
          }`}
          onClick={() => fileInputRef.current?.click()}
        >
          <p className="text-sm text-[var(--color-text-muted)]">
            SRT 또는 TXT 파일을 드래그하거나 클릭하여 업로드
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".srt,.txt"
          multiple
          className="hidden"
          onChange={(e) => handleUpload(e.target.files)}
        />
      </section>

      {/* 선택 과목 연동 정보 */}
      {uploadCourse && courseInfo && (
        <section className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">School Sync 연동 — {uploadCourse}</h2>
            {courseInfo.lastCrawl && (
              <span className="text-[11px] text-[var(--color-text-muted)]">
                마지막 크롤링: {new Date(courseInfo.lastCrawl).toLocaleString("ko-KR")}
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-[var(--color-text-muted)]">학습 컨텍스트: </span>
              <span className={courseInfo.hasContext ? "text-emerald-400" : "text-red-400"}>
                {courseInfo.hasContext ? "준비됨" : "없음 — 크롤링 필요"}
              </span>
            </div>
            <div>
              <span className="text-[var(--color-text-muted)]">수업자료: </span>
              <span>{courseInfo.materials.length > 0 ? `${courseInfo.materials.length}개 파일` : "없음"}</span>
              {courseInfo.materials.length > 0 && (
                <span className="text-[var(--color-text-muted)] ml-1">
                  ({courseInfo.materials.map((m) => m.filename.split(".").pop()?.toUpperCase()).filter((v, i, a) => a.indexOf(v) === i).join(", ")})
                </span>
              )}
            </div>
          </div>
        </section>
      )}

      {/* 업로드된 파일 + 패키징 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 업로드된 파일 목록 */}
        <section className="bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
            <h2 className="text-sm font-semibold">전사본 파일 ({totalFiles})</h2>
            <button
              onClick={() => triggerPack()}
              disabled={isRunning || totalFiles === 0}
              className="px-3 py-1 bg-amber-600 text-white rounded text-xs font-medium hover:bg-amber-700 disabled:opacity-50 transition-colors"
            >
              {isRunning && taskStatus?.task_type === "pack" ? "패키징 중..." : "전체 패키징"}
            </button>
          </div>
          <div className="divide-y divide-[var(--color-border)] max-h-80 overflow-y-auto">
            {dagloFiles.length === 0 ? (
              <p className="p-4 text-sm text-[var(--color-text-muted)]">업로드된 파일이 없습니다</p>
            ) : (
              dagloFiles.map((c) => (
                <div key={c.course} className="p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{c.course}</span>
                    <button
                      onClick={() => triggerPack(c.course)}
                      disabled={isRunning}
                      className="text-xs text-amber-500 hover:text-amber-400 disabled:opacity-50"
                    >
                      패키징
                    </button>
                  </div>
                  <div className="space-y-1">
                    {c.files.map((f) => (
                      <div key={f.filename} className="flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                        <span>
                          {f.date && <span className="text-[var(--color-primary)] mr-1.5">{f.date}</span>}
                          {f.filename}
                          <span className="ml-1.5 opacity-60">{formatSize(f.size)}</span>
                        </span>
                        <button
                          onClick={() => handleDelete(c.course, f.filename)}
                          className="text-red-400 hover:text-red-300 ml-2"
                        >
                          삭제
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* 생성된 패키지 */}
        <section className="bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
          <div className="px-4 py-3 border-b border-[var(--color-border)]">
            <h2 className="text-sm font-semibold">NotebookLM 패키지</h2>
          </div>
          <div className="divide-y divide-[var(--color-border)] max-h-80 overflow-y-auto">
            {packages.length === 0 ? (
              <p className="p-4 text-sm text-[var(--color-text-muted)]">생성된 패키지가 없습니다</p>
            ) : (
              packages.map((p) => (
                <div key={p.course} className="p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{p.course}</span>
                    <div className="flex gap-2">
                      {gdriveEnabled && (
                        <button
                          onClick={() => uploadToDrive(p.course)}
                          disabled={uploadingToDrive === p.course}
                          className="text-xs text-emerald-400 hover:underline disabled:opacity-50"
                        >
                          {uploadingToDrive === p.course ? "업로드 중..." : "Drive 내보내기"}
                        </button>
                      )}
                      <button
                        onClick={() => downloadAll(p.course, p.files)}
                        className="text-xs text-[var(--color-primary)] hover:underline"
                      >
                        전체 다운로드
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1">
                    {p.files.map((f) => (
                      <div key={f.filename} className="flex items-center justify-between text-xs">
                        <span className={f.changed === false ? "text-[var(--color-text-muted)] opacity-50" : "text-[var(--color-text-muted)]"}>
                          {f.filename}
                          <span className="ml-1.5 opacity-60">{formatSize(f.size)}</span>
                          {f.changed === true && <span className="ml-1.5 text-blue-400 text-[10px]">변경됨</span>}
                          {f.changed === false && <span className="ml-1.5 text-[var(--color-text-muted)] text-[10px]">동일</span>}
                        </span>
                        <a
                          href={`/api/la/packages/${encodeURIComponent(p.course)}/${encodeURIComponent(f.filename)}`}
                          download
                          className="text-[var(--color-primary)] hover:underline ml-2"
                        >
                          다운로드
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {/* 실행 로그 */}
      {logs.length > 0 && (
        <section className="bg-[var(--color-bg)] rounded-lg border border-[var(--color-border)] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-[var(--color-surface)] border-b border-[var(--color-border)]">
            <h2 className="text-xs font-semibold text-[var(--color-text-muted)]">실행 로그</h2>
            {taskStatus && taskStatus.status !== "idle" && (
              <span className={`text-xs ${
                taskStatus.status === "running" ? "text-blue-400"
                  : taskStatus.status === "completed" ? "text-emerald-400"
                    : "text-red-400"
              }`}>
                {taskStatus.status === "running" ? "실행 중" : taskStatus.status === "completed" ? "완료" : "실패"}
              </span>
            )}
          </div>
          <div className="p-4 max-h-64 overflow-y-auto font-mono text-xs leading-relaxed">
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
