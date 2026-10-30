import { useState } from "react";
import { streamChat, type Msg } from "./lib/stream";

export default function App() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const history: Msg[] = [...messages, { role: "user", content: text }];
    setMessages([...history, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);
    try {
      await streamChat(history, (t) =>
        setMessages((m) => {
          const last = m[m.length - 1];
          return [...m.slice(0, -1), { ...last, content: last.content + t }];
        }),
      );
    } catch (e) {
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: "assistant", content: `Error: ${e}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex h-screen max-w-2xl flex-col p-4">
      <div className="flex-1 space-y-3 overflow-y-auto">
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "ml-auto w-fit max-w-[80%] whitespace-pre-wrap rounded bg-blue-600 p-2 text-white"
                : "max-w-[80%] whitespace-pre-wrap rounded bg-gray-100 p-2 text-gray-900"
            }
          >
            {m.content}
          </div>
        ))}
      </div>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          className="flex-1 rounded border p-2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Nhập tin nhắn..."
        />
        <button
          className="rounded bg-blue-600 px-4 text-white disabled:opacity-50"
          disabled={busy}
        >
          Gửi
        </button>
      </form>
    </div>
  );
}
