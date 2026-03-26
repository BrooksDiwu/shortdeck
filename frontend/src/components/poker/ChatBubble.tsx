import { useState, useRef, useEffect } from "react";
import { MessageCircle, Send } from "lucide-react";

const MESSAGES = [
  { user: "Phil", text: "Nice hand!" },
  { user: "Sara", text: "gg" },
  { user: "Mike", text: "All in next round 😤" },
];

const ChatBubble = () => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState(MESSAGES);
  const [input, setInput] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const send = () => {
    if (!input.trim()) return;
    setMessages((m) => [...m, { user: "You", text: input.trim() }]);
    setInput("");
  };

  return (
    <>
      {/* Bubble trigger */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="absolute bottom-3 right-3 z-50 w-10 h-10 rounded-full bg-secondary border border-border flex items-center justify-center shadow-lg active:scale-95 transition-transform"
        >
          <MessageCircle className="w-5 h-5 text-primary" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div
          ref={panelRef}
          className="absolute bottom-14 right-3 z-50 w-56 h-64 bg-card border border-border rounded-lg shadow-2xl flex flex-col overflow-hidden"
        >
          <div className="px-3 py-2 border-b border-border text-xs font-bold text-primary">
            Table Chat
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5">
            {messages.map((m, i) => (
              <div key={i} className="text-[11px]">
                <span className="font-bold text-primary">{m.user}: </span>
                <span className="text-foreground">{m.text}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center border-t border-border p-1.5 gap-1">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Type..."
              className="flex-1 bg-secondary text-foreground text-[11px] rounded px-2 py-1 outline-none placeholder:text-muted-foreground"
            />
            <button onClick={send} className="text-primary active:scale-90 transition-transform">
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default ChatBubble;
