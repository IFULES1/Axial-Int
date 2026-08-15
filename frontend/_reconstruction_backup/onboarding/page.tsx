"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Button, Field, Input, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STEPS = [
  { key: "company_name", label: "Nom de l'entreprise", placeholder: "Axial Intelligence", required: true },
  { key: "sector", label: "Secteur", placeholder: "SaaS B2B, Fintech, HealthTech…" },
  { key: "funding_stage", label: "Stade de financement", placeholder: "Pre-seed, Seed, Série A…" },
  { key: "target_market", label: "Marché cible", placeholder: "France, Europe, PME industrielles…" },
  { key: "main_challenge", label: "Défi principal du moment", placeholder: "Acquisition, levée, positionnement…" },
] as const;

export default function OnboardingPage() {
  const router = useRouter();
  const { user, token, loading, refresh } = useAuth();
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/auth");
    if (!loading && user?.onboarding_complete) router.replace("/workspace");
  }, [loading, user, router]);

  if (loading || !user) return <Centered><Spinner label="Chargement…" /></Centered>;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.put("/memory/profile", values, token);
      await refresh();
      router.push("/workspace");
    } catch {
      setError("Impossible d'enregistrer le profil. Réessaie.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold">Parle-nous de ton entreprise</h1>
      <p className="mt-2 text-sm text-fg-muted">
        Ce contexte est injecté automatiquement dans chaque analyse — tu ne te réexpliqueras jamais.
      </p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        {STEPS.map((s) => (
          <Field key={s.key} label={s.label + (s.required ? " *" : "")}>
            <Input
              required={s.required}
              placeholder={s.placeholder}
              value={values[s.key] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [s.key]: e.target.value }))}
            />
          </Field>
        ))}
        {error && <Alert>{error}</Alert>}
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "…" : "Accéder à mon workspace"}
        </Button>
      </form>
    </main>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-screen items-center justify-center">{children}</div>;
}
