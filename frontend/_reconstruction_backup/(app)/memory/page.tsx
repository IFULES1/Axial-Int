"use client";

import { useEffect, useState } from "react";
import { Button, Card, Field, Input, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const FIELDS = [
  ["company_name", "Nom de l'entreprise"],
  ["sector", "Secteur"],
  ["positioning", "Positionnement"],
  ["funding_stage", "Stade de financement"],
  ["team_size", "Taille d'équipe"],
  ["country", "Pays"],
  ["target_market", "Marché cible"],
  ["client_segment", "Segment client"],
  ["known_competitors", "Concurrents connus"],
  ["main_challenge", "Défi principal"],
] as const;

export default function MemoryPage() {
  const { token, refresh } = useAuth();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .get<Record<string, string> | null>("/memory/profile", token)
      .then((p) => {
        if (p) {
          const clean: Record<string, string> = {};
          for (const [k] of FIELDS) clean[k] = (p[k] as string) ?? "";
          setValues(clean);
        }
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSaving(true);
    setSaved(false);
    try {
      await api.put("/memory/profile", values, token);
      await refresh();
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-8">
      <h1 className="text-lg font-semibold">Mémoire</h1>
      <p className="mt-1 text-sm text-fg-muted">
        Ce contexte est injecté automatiquement dans chaque analyse et conversation.
      </p>

      <Card className="mt-6">
        {loading ? (
          <Spinner label="Chargement…" />
        ) : (
          <form onSubmit={save} className="space-y-4">
            {FIELDS.map(([key, label]) => (
              <Field key={key} label={label}>
                <Input
                  value={values[key] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                />
              </Field>
            ))}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={saving}>
                {saving ? "…" : "Enregistrer"}
              </Button>
              {saved && <span className="text-sm text-success">Enregistré ✓</span>}
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}
