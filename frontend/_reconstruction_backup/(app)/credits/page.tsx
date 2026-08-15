"use client";

import { useEffect, useState } from "react";
import { Card, Pill, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Balance = {
  available: number;
  trial_credits: number;
  free_credits: number;
  purchased_credits: number;
  trial_active: boolean;
};
type Plan = {
  key: string;
  name: string;
  price_usd: number | null;
  period: string;
  monthly_credits: number | null;
  features: string[];
};

function tone(available: number) {
  if (available > 60) return "text-success";
  if (available >= 24) return "text-warning";
  return "text-error";
}

export default function CreditsPage() {
  const { token } = useAuth();
  const [balance, setBalance] = useState<Balance | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);

  useEffect(() => {
    if (!token) return;
    api.get<Balance>("/billing/balance", token).then(setBalance);
    api.get<{ plans: Plan[] }>("/billing/plans").then((d) => setPlans(d.plans));
  }, [token]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-lg font-semibold">Crédits</h1>
      <p className="mt-1 text-sm text-fg-muted">Chaque analyse consomme des crédits selon sa complexité.</p>

      {!balance ? (
        <div className="mt-6">
          <Spinner label="Chargement…" />
        </div>
      ) : (
        <Card className="mt-6">
          <div className="flex items-end justify-between">
            <div>
              <div className="text-sm text-fg-muted">Solde disponible</div>
              <div className={`mt-1 text-4xl font-semibold ${tone(balance.available)}`}>
                {balance.available}
              </div>
            </div>
            {balance.trial_active && <Pill active>Essai actif</Pill>}
          </div>
          <div className="mt-4 flex gap-4 text-xs text-fg-muted">
            <span>Essai : {balance.trial_credits}</span>
            <span>Gratuits : {balance.free_credits}</span>
            <span>Achetés : {balance.purchased_credits}</span>
          </div>
        </Card>
      )}

      <h2 className="mb-3 mt-8 text-sm font-medium text-fg-muted">Plans</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {plans.map((p) => (
          <Card key={p.key}>
            <div className="flex items-center justify-between">
              <h3 className="font-medium">{p.name}</h3>
              <span className="text-sm text-v-soft">
                {p.price_usd === null ? "Sur devis" : p.price_usd === 0 ? "Gratuit" : `$${p.price_usd}`}
              </span>
            </div>
            <div className="mt-1 text-xs text-fg-muted">
              {p.monthly_credits ? `${p.monthly_credits} crédits` : "Crédits sur mesure"} · {p.period}
            </div>
            <ul className="mt-3 space-y-1.5">
              {p.features.map((f) => (
                <li key={f} className="flex gap-2 text-xs text-fg-muted">
                  <span className="text-v-soft">•</span>
                  {f}
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}
