"use client";

import { type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "subtle" }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-button px-4 py-2.5 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
  const styles = {
    primary: "bg-v-bright text-on-violet hover:opacity-90",
    ghost: "border border-border hover:border-v-soft",
    subtle: "bg-surface text-fg hover:bg-white/5",
  }[variant];
  return (
    <button className={`${base} ${styles} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-input border border-border bg-surface px-3.5 py-2.5 text-sm text-fg outline-none transition placeholder:text-fg-muted focus:border-v-soft ${className}`}
      {...props}
    />
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-fg-muted">{label}</span>
      {children}
    </label>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-card border border-border bg-surface p-5 ${className}`}>{children}</div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-fg-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-v-soft border-t-transparent" />
      {label}
    </div>
  );
}

export function Alert({ kind = "error", children }: { kind?: "error" | "info"; children: ReactNode }) {
  const color = kind === "error" ? "text-error border-error/40" : "text-v-soft border-v-soft/40";
  return (
    <div className={`rounded-input border px-3.5 py-2.5 text-sm ${color}`}>{children}</div>
  );
}

export function Pill({ children, active = false }: { children: ReactNode; active?: boolean }) {
  return (
    <span
      className={`rounded-pill px-3 py-1 text-xs ${
        active ? "bg-v-bright text-on-violet" : "border border-border text-fg-muted"
      }`}
    >
      {children}
    </span>
  );
}
