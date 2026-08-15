"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/workspace", label: "Workspace", icon: "◇" },
  { href: "/agents", label: "Agents", icon: "◈" },
  { href: "/reports", label: "Rapports", icon: "▤" },
  { href: "/memory", label: "Mémoire", icon: "◉" },
  { href: "/credits", label: "Crédits", icon: "◆" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, token, loading, logout } = useAuth();
  const [credits, setCredits] = useState<number | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/auth");
    if (!loading && user && !user.onboarding_complete) router.replace("/onboarding");
  }, [loading, user, router]);

  useEffect(() => {
    if (token) {
      api
        .get<{ available: number }>("/billing/balance", token)
        .then((b) => setCredits(b.available))
        .catch(() => setCredits(null));
    }
  }, [token, pathname]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <Spinner label="Chargement…" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg text-fg md:flex">
      {/* Sidebar (desktop) / top nav (mobile) */}
      <aside className="flex shrink-0 flex-col border-b border-border md:h-screen md:w-60 md:border-b-0 md:border-r">
        <div className="flex items-center justify-between px-4 py-4 md:px-5">
          <Link href="/workspace" className="flex items-center gap-2">
            <div className="h-6 w-6 rounded-md bg-gradient-to-br from-v-bright to-v-deep" />
            <span className="font-mono text-sm font-semibold">Axial</span>
          </Link>
          <span className="rounded-pill border border-border px-2.5 py-1 text-xs text-v-soft md:hidden">
            {credits ?? "—"} cr
          </span>
        </div>

        <nav className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-1 md:flex-col md:overflow-visible md:px-3">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 whitespace-nowrap rounded-input px-3 py-2 text-sm transition ${
                  active ? "bg-v-bright/15 text-fg" : "text-fg-muted hover:bg-white/5 hover:text-fg"
                }`}
              >
                <span className="text-v-soft">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden border-t border-border px-3 py-3 md:block">
          <div className="mb-2 flex items-center justify-between px-2 text-xs text-fg-muted">
            <span>Crédits</span>
            <span className="text-v-soft">{credits ?? "—"}</span>
          </div>
          <div className="truncate px-2 text-xs text-fg-muted">{user.email}</div>
          <button
            onClick={() => {
              logout();
              router.replace("/");
            }}
            className="mt-2 w-full rounded-input px-2 py-1.5 text-left text-xs text-fg-muted hover:bg-white/5"
          >
            Se déconnecter
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
