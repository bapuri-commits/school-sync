import type { Course, CourseDetail, DashboardData, Notice, UserInfo } from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export type SSEChunk = { type: "text"; text: string } | { type: "done" } | { type: "error"; text: string };

export const api = {
  me: () => get<UserInfo>("/me"),
  dashboard: () => get<DashboardData>("/dashboard"),
  courses: () => get<Course[]>("/courses"),
  course: (name: string) => get<CourseDetail>(`/courses/${encodeURIComponent(name)}`),
  notices: () => get<Notice[]>("/notices"),

  askStream: async function* (question: string, webSearch: boolean = true, sessionId: string = "default"): AsyncGenerator<SSEChunk> {
    const res = await fetch(`${BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, web_search: webSearch, session_id: sessionId }),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop()!;
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            yield JSON.parse(line.slice(6)) as SSEChunk;
          } catch { /* skip malformed */ }
        }
      }
    }
  },

  askReset: (sessionId: string = "default") =>
    fetch(`${BASE}/ask/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    }),
};
