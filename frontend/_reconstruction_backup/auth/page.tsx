"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, Button, Field, Input } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AuthPage() {
  const router = useRouter();
  const { register, login } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const user =
        mode === "register"
          ? await register(email, password, fullName)
          : await login(email, password);
      router.push(user.onboarding_complete ? "/workspace" : "/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6 py-12">
      <div className="w-full max-w-md">
        <Link href="/" className="mb-8 flex items-center gap-2">
          <div className="h-6 w-6 rounded-md bg-gradient-to-br from-v-bright to-v-deep" />
          <span className="font-mono text-sm font-semibold">Axial Intelligence</span>
        </Link>

        <div className="mb-6 flex gap-1 rounded-input border border-border p-1">
          {(["register", "login"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 rounded-[7px] px-4 py-2 text-sm font-medium transition ${
                mode === m ? "bg-v-bright text-on-violet" : "text-fg-muted hover:text-fg"
              }`}
            >
              {m === "register" ? "Créer un compte" : "Se connecter"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === "register" && (
            <Field label="Nom complet">
              <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Jane Founder" />
            </Field>
          )}
          <Field label="Email professionnel">
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@startup.com"
            />
          </Field>
          <Field label="Mot de passe">
            <Input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="8 caractères minimum"
            />
          </Field>

          {error && <Alert>{error}</Alert>}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "…" : mode === "register" ? "Créer mon compte" : "Se connecter"}
          </Button>
        </form>

        {mode === "register" && (
          <p className="mt-4 text-center text-xs text-fg-muted">
            120 crédits offerts · 14 jours · email professionnel requis
          </p>
        )}
      </div>
    </main>
  );
}
