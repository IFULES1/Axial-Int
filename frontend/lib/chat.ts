import { api } from "./api";

export type Message = {
  id: string;
  role: "user" | "assistant";
  agent: string | null;
  content: string;
  citations: unknown[] | null;
  created_at: string;
};

type Project = { id: string; name: string };
type Conversation = { id: string; default_agent: string };

/** Ensure a default project + conversation exist; return the conversation id. */
export async function ensureConversation(token: string, defaultAgent = "market_scanner"): Promise<string> {
  let projects = await api.get<Project[]>("/intelligence/projects", token);
  if (projects.length === 0) {
    const p = await api.post<Project>("/intelligence/projects", { name: "Workspace" }, token);
    projects = [p];
  }
  const projectId = projects[0].id;

  const convs = await api.get<Conversation[]>(
    `/intelligence/projects/${projectId}/conversations`,
    token,
  );
  if (convs.length > 0) return convs[0].id;

  const c = await api.post<Conversation>(
    `/intelligence/projects/${projectId}/conversations`,
    { title: "Workspace", default_agent: defaultAgent },
    token,
  );
  return c.id;
}

export async function loadMessages(token: string, conversationId: string): Promise<Message[]> {
  return api.get<Message[]>(`/intelligence/conversations/${conversationId}/messages`, token);
}

export async function sendMessage(
  token: string,
  conversationId: string,
  content: string,
  agent?: string,
): Promise<Message> {
  return api.post<Message>(
    `/intelligence/conversations/${conversationId}/messages`,
    { content, agent: agent ?? null },
    token,
  );
}
