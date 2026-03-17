import { useCallback, useRef, useState } from "react";

interface TaskStatus {
  status: "idle" | "running" | "completed" | "failed";
  task_type: string;
  started_at: string;
  finished_at: string;
  exit_code: number | null;
  log_lines?: number;
}

type SSEChunk =
  | { type: "log"; text: string }
  | { type: "status"; status: string; exit_code: number | null }
  | { type: "done" };

interface UseLogStreamOptions {
  onStreamEnd?: () => void;
}

export function useLogStream(options: UseLogStreamOptions = {}) {
  const [logs, setLogs] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const onStreamEndRef = useRef(options.onStreamEnd);
  onStreamEndRef.current = options.onStreamEnd;

  const startLogStream = useCallback(async () => {
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
      if (!res.body) {
        setStreaming(false);
        return;
      }
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
                prev
                  ? { ...prev, status: chunk.status as TaskStatus["status"], exit_code: chunk.exit_code }
                  : prev
              );
            }
          } catch {
            /* skip malformed SSE */
          }
        }
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
    } finally {
      if (flushTimer) clearInterval(flushTimer);
      flush();
    }

    setStreaming(false);
    onStreamEndRef.current?.();
  }, []);

  const clearLogs = useCallback(() => setLogs([]), []);

  const abort = useCallback(() => abortRef.current?.abort(), []);

  const fetchTaskStatus = useCallback(async () => {
    try {
      const r = await fetch("/api/sync/status");
      if (r.ok) {
        const data: TaskStatus = await r.json();
        setTaskStatus(data);
        if (data.status === "running") startLogStream();
      }
    } catch {
      /* ignore */
    }
  }, [startLogStream]);

  return {
    logs,
    streaming,
    taskStatus,
    setTaskStatus,
    startLogStream,
    clearLogs,
    abort,
    fetchTaskStatus,
  };
}

export type { TaskStatus, SSEChunk };
