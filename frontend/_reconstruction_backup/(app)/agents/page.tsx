"use client";

import { useEffect, useState } from "react";
import { Button, Card, Input, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Agent = { key: string; name: string; framework: string };

const DETAILS: Record<string, { for: string; not: string }> = {
  market_scanner: {
    for: "Forces macro : attractivité marché, régulation, tendances, entrée sur un marché, expansion.",
    not: "L'analyse concurrentielle directe → redirige vers Competitor Radar.",
  },
  competitor_radar: {
    for: "5 forces de Porter : rivalité, nouveaux entrants, substituts, pouvoir acheteurs/fournisseurs.",
    not: "Les forces macro larges → redirige vers Market Scanner.",
  },
};

export default function AgentsPage() {
  const { token } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [query, setQuery] = useState("");
  const [routed, setRouted] = useState<{ name: string | null; redirect_note: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<{ agents: Agent[] }>("/intelligence/agents").then((d) => setAgents(d.agents));
  }, []);

  async function testRoute(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || !token) return;
    setBusy(true);
    try {
      setRouted(await api.post("/intelligence/agents/route", { query }, token));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-lg font-semibold">Agents stratégiques</h1>
      <p className="mt-1 text-sm text-fg-muted">
        Deux agents natifs, non-chevauchants. Chaque réponse se termine par un bloc « AXIAL Recommande ».
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {agents.length === 0 ? (
          <Spinner label="Chargement…" />
        ) : (
          agents.map((a) => (
            <Card key={a.key}>
              <div className="mb-1 flex items-center justify-between">
                <h3 className="font-medium">{a.name}</h3>
                <span className="rounded-pill border border-border px-2.5 py-0.5 text-xs text-v-soft">
                  {a.framework}
                </span>
              </div>
              <p className="mt-2 text-sm text-fg-muted">
                <span className="text-fg">Pour :</span> {DETAILS[a.key]?.for}
              </p>
              <p className="mt-1.5 text-sm text-fg-muted">
                <span className="text-fg">Pas pour :</span> {DETAILS[a.key]?.not}
              </p>
            </Card>
          ))
        )}
      </div>

      <Card className="mt-6">
        <h3 className="mb-3 text-sm font-medium">Quel agent pour ma question ?</h3>
        <form onSubmit={testRoute} className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ex : mes concurrents baissent leurs prix, que faire ?"
          />
          <Button type="submit" disabled={busy || !query.trim()}>
            Router
          </Button>
        </form>
        {routed && (
          <p className="mt-3 text-sm">
            → <span className="text-v-soft">{routed.name}</span>
            {routed.redirect_note && (
              <span className="mt-1 block text-xs text-fg-muted">ℹ️ {routed.redirect_note}</span>
            )}
          </p>
        )}
      </Card>
    </div>
  );
}
