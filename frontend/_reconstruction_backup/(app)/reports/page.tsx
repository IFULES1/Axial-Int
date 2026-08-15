"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, Field, Input, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type AnalysisType = { key: string; label: string };
type Report = { id: string; title: string; analysis_type: string; created_at: string };
type RunResult = { title: string; content: string; degraded: boolean };

export default function ReportsPage() {
  const { token } = useAuth();
  const [types, setTypes] = useState<AnalysisType[]>([]);
  const [type, setType] = useState("etude_marche");
  const [query, setQuery] = useState("");
  const [reports, setReports] = useState<Report[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = () => token && api.get<Report[]>("/reports", token).then(setReports);

  useEffect(() => {
    api.get<{ types: AnalysisType[] }>("/analysis/types").then((d) => setTypes(d.types));
    reload();
  }, [token]);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !query.trim()) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.post<RunResult>("/analysis/run", { query, analysis_type: type }, token);
      setResult(res);
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur lors de la génération.");
    } finally {
      setRunning(false);
    }
  }

  async function downloadPdf(id: string, title: string) {
    if (!token) return;
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    const res = await fetch(`${base}/reports/${id}/pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-lg font-semibold">Rapports</h1>
      <p className="mt-1 text-sm text-fg-muted">Génère une analyse structurée, archivée et exportable en PDF.</p>

      <Card className="mt-6">
        <form onSubmit={run} className="space-y-4">
          <Field label="Type d'analyse">
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full rounded-input border border-border bg-surface px-3.5 py-2.5 text-sm outline-none focus:border-v-soft"
            >
              {types.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Sujet / question">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ex : le marché de la fintech B2B en France en 2026"
            />
          </Field>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" disabled={running || !query.trim()}>
            {running ? "Génération…" : "Générer l'analyse"}
          </Button>
        </form>
      </Card>

      {running && (
        <div className="mt-4">
          <Spinner label="Recherche web + rédaction (peut prendre ~30 s)…" />
        </div>
      )}

      {result && (
        <Card className="mt-4">
          {result.degraded && <Alert kind="info">Mode dégradé — recherche web indisponible.</Alert>}
          <h3 className="mt-2 font-medium">{result.title}</h3>
          <div className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-fg-muted">
            {result.content}
          </div>
        </Card>
      )}

      <h2 className="mb-3 mt-8 text-sm font-medium text-fg-muted">Archive</h2>
      <div className="space-y-2">
        {reports.length === 0 && <p className="text-sm text-fg-muted">Aucun rapport pour l'instant.</p>}
        {reports.map((r) => (
          <div
            key={r.id}
            className="flex items-center justify-between rounded-card border border-border bg-surface px-4 py-3"
          >
            <div className="min-w-0">
              <div className="truncate text-sm">{r.title}</div>
              <div className="text-xs text-fg-muted">{new Date(r.created_at).toLocaleDateString("fr-FR")}</div>
            </div>
            <Button variant="ghost" onClick={() => downloadPdf(r.id, r.title)}>
              PDF
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
