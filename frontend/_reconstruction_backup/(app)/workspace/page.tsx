"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Input, Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { ensureConversation, loadMessages, sendMessage, type Message } from "@/lib/chat";

const STARTERS = [
  "Quelles sont les tendances macro de mon marché cette année ?",
  "Qui sont mes principaux concurrents et comment se positionnent-ils ?",
  "Quels risques réglementaires devrais-je surveiller ?",
  "Où sont les opportunités de différenciation dans mon secteur ?",
];

export default function WorkspacePage() {
  const { token } = useAuth();
  const [convId, setConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [ready, setReady] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!token) return;
    ensureConversation(token)
      .then(async (id) => {
        setConvId(id);
        setMessages(await loadMessages(token, id));
      })
      .finally(() => setReady(true));
  }, [token]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function submit(text: string) {
    if (!token || !convId || !text.trim() || sending) return;
    setInput("");
    setSending(true);
    const optimistic: Message = {
      id: `tmp-${Date.now()}`,
      role: "user",
      agent: null,
      content: text,
      citations: null,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, optimistic]);
    try {
      await sendMessage(token, convId, text);
      setMessages(await loadMessages(token, convId));
    } catch {
      setMessages((m) => [
        ...m,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          agent: null,
          content: "⚠️ Une erreur est survenue (crédits insuffisants ou service indisponible).",
          citations: null,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-0px)] flex-col md:h-screen">
      <header className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold">Workspace</h1>
        <p className="text-sm text-fg-muted">Pose n'importe quelle question — réponse sourcée.</p>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
        {!ready ? (
          <Spinner label="Préparation…" />
        ) : messages.length === 0 ? (
          <div className="mx-auto max-w-2xl">
            <p className="mb-4 text-sm text-fg-muted">Pour démarrer :</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => submit(s)}
                  className="rounded-card border border-border bg-surface p-4 text-left text-sm transition hover:border-v-soft"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-2xl space-y-5">
            {messages.map((m) => (
              <MessageBubble key={m.id} m={m} />
            ))}
            {sending && <Spinner label="Analyse en cours…" />}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="border-t border-border p-4"
      >
        <div className="mx-auto flex max-w-2xl gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Pose ta question…"
            disabled={!ready || sending}
          />
          <Button type="submit" disabled={!ready || sending || !input.trim()}>
            Envoyer
          </Button>
        </div>
      </form>
    </div>
  );
}

function MessageBubble({ m }: { m: Message }) {
  const isUser = m.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : ""}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-card px-4 py-3 text-sm leading-relaxed ${
          isUser ? "bg-v-bright text-on-violet" : "border border-border bg-surface"
        }`}
      >
        {!isUser && m.agent && (
          <div className="mb-1.5 text-xs font-medium text-v-soft">
            {m.agent === "competitor_radar" ? "Competitor Radar" : "Market Scanner"}
          </div>
        )}
        {m.content}
      </div>
    </div>
  );
}
