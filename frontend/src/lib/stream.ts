export type Msg = { role: "user" | "assistant"; content: string };

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function streamChat(
  messages: Msg[],
  onToken: (t: string) => void,
) {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    onToken(decoder.decode(value, { stream: true }));
  }
}
