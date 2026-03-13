import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import type { Permission } from "../types";

const NAV: { to: string; label: string; perm: Permission }[] = [
  { to: "/", label: "대시보드", perm: "dashboard" },
  { to: "/ask", label: "AI Q&A", perm: "ask" },
  { to: "/lesson-assist", label: "Lesson Assist", perm: "sync" },
  { to: "/sync", label: "동기화", perm: "sync" },
];

export default function Layout() {
  const { pathname } = useLocation();
  const { user, loading, error } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-[var(--color-text-muted)]">인증 확인 중...</p>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 font-semibold text-lg mb-2">접근 불가</p>
          <p className="text-[var(--color-text-muted)] text-sm mb-4">{error ?? "인증 정보가 없습니다"}</p>
          <a
            href="https://syworkspace.cloud/login"
            className="px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg text-sm hover:bg-[var(--color-primary-dark)] transition-colors"
          >
            SyOps 로그인
          </a>
        </div>
      </div>
    );
  }

  const visibleNav = NAV.filter((n) => user.permissions.includes(n.perm));

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link to="/" className="text-lg font-bold tracking-tight">
              StudyHub
            </Link>
            <nav className="flex gap-1">
              {visibleNav.map((n) => (
                <Link
                  key={n.to}
                  to={n.to}
                  className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                    pathname === n.to
                      ? "bg-[var(--color-primary)] text-white"
                      : "text-[var(--color-text-muted)] hover:text-white hover:bg-[var(--color-surface-hover)]"
                  }`}
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
          <span className="text-xs text-[var(--color-text-muted)]">
            {user.username} ({user.role})
          </span>
        </div>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
