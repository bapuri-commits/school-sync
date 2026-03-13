import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import type { Permission } from "../types";

const SYOPS_LOGIN = "https://syworkspace.cloud/login";

interface NavItem {
  to: string;
  label: string;
  perm: Permission;
}

interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    id: "school-sync",
    label: "School Sync",
    items: [
      { to: "/", label: "대시보드", perm: "dashboard" },
      { to: "/ask", label: "AI Q&A", perm: "ask" },
      { to: "/sync", label: "동기화", perm: "sync" },
    ],
  },
  {
    id: "lesson-assist",
    label: "Lesson Assist",
    items: [
      { to: "/lesson-assist", label: "전사본 / 패키징", perm: "sync" },
    ],
  },
];

function isActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/" || pathname.startsWith("/courses/");
  return pathname.startsWith(to);
}

function getGroupForPath(pathname: string): string {
  for (const g of NAV_GROUPS) {
    if (g.items.some((i) => isActive(pathname, i.to))) return g.id;
  }
  return "school-sync";
}

export default function Layout() {
  const { pathname } = useLocation();
  const { user, loading, error } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => { setSidebarOpen(false); }, [pathname]);

  useEffect(() => {
    if ((error || !user) && !loading) {
      const url = `${SYOPS_LOGIN}?redirect=${encodeURIComponent(window.location.href)}`;
      const t = setTimeout(() => { window.location.href = url; }, 1500);
      return () => clearTimeout(t);
    }
  }, [error, user, loading]);

  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = ""; };
    }
  }, [sidebarOpen]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-[var(--color-text-muted)]">인증 확인 중...</p>
      </div>
    );
  }

  if (error || !user) {
    const redirect = `${SYOPS_LOGIN}?redirect=${encodeURIComponent(window.location.href)}`;
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-[var(--color-text-muted)] text-sm mb-4">SyOps 로그인으로 이동합니다...</p>
          <a
            href={redirect}
            className="px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg text-sm hover:bg-[var(--color-primary-dark)] transition-colors"
          >
            로그인 페이지로 이동
          </a>
        </div>
      </div>
    );
  }

  const activeGroup = getGroupForPath(pathname);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)] shrink-0">
        <div className="px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className="md:hidden p-1.5 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
              aria-label="메뉴"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
              </svg>
            </button>
            <Link to="/" className="text-lg font-bold tracking-tight">StudyHub</Link>
          </div>
          <span className="text-xs text-[var(--color-text-muted)]">
            {user.username} ({user.role})
          </span>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside
          className={`
            fixed md:static inset-y-0 left-0 z-40 w-56 bg-[var(--color-surface)] border-r border-[var(--color-border)]
            transform transition-transform md:transform-none md:translate-x-0 pt-14 md:pt-0
            ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          `}
        >
          <nav className="p-3 space-y-4 overflow-y-auto h-full">
            {NAV_GROUPS.map((group) => {
              const visible = group.items.filter((i) => user.permissions.includes(i.perm));
              if (visible.length === 0) return null;
              const isGroupActive = activeGroup === group.id;

              return (
                <div key={group.id}>
                  <h3
                    className={`px-2 mb-1.5 text-[11px] font-semibold uppercase tracking-wider ${
                      isGroupActive ? "text-[var(--color-primary)]" : "text-[var(--color-text-muted)]"
                    }`}
                  >
                    {group.label}
                  </h3>
                  <div className="space-y-0.5">
                    {visible.map((item) => (
                      <Link
                        key={item.to}
                        to={item.to}
                        className={`block px-3 py-2 rounded-md text-sm transition-colors ${
                          isActive(pathname, item.to)
                            ? "bg-[var(--color-primary)] text-white"
                            : "text-[var(--color-text-muted)] hover:text-white hover:bg-[var(--color-surface-hover)]"
                        }`}
                      >
                        {item.label}
                      </Link>
                    ))}
                  </div>
                </div>
              );
            })}
          </nav>
        </aside>

        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/50 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
