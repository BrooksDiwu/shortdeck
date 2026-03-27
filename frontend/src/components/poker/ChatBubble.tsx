import { useState, useRef, useEffect } from "react";
import { MessageCircle, Send } from "lucide-react";
import { useGameStore } from "@/stores/gameStore";

const ChatBubble = () => {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [unread, setUnread] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatMessages = useGameStore((s) => s.chatMessages);
  const sendMessage = useGameStore((s) => s.sendMessage);

  const prevLengthRef = useRef(chatMessages.length);
  useEffect(() => {
    if (!open && chatMessages.length > prevLengthRef.current) {
      setUnread((u) => u + (chatMessages.length - prevLengthRef.current));
    }
    prevLengthRef.current = chatMessages.length;
  }, [chatMessages.length, open]);

  useEffect(() => {
    if (open) setUnread(0);
  }, [open]);

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

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages, open]);

  const send = () => {
    const text = input.trim();
    if (!text) return;
    sendMessage({ type: "chat_message", text });
    setInput("");
  };

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="absolute bottom-3 right-3 z-50 w-10 h-10 rounded-full bg-secondary border border-border flex items-center justify-center shadow-lg active:scale-95 transition-transform"
        >
          <MessageCircle className="w-5 h-5 text-primary" />
          {unread > 0 && (
            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      )}

      {open && (
        <div
          ref={panelRef}
          className="absolute bottom-14 right-3 z-50 w-56 h-64 bg-card border border-border rounded-lg shadow-2xl flex flex-col overflow-hidden"
        >
          <div className="px-3 py-2 border-b border-border text-xs font-bold text-primary">
            Table Chat
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5">
            {chatMessages.length === 0 && (
              <p className="text-[11px] text-muted-foreground text-center mt-4">No messages yet</p>
            )}
            {chatMessages.map((m, i) => (
              <div key={i} className="text-[11px]">
                <span className="font-bold text-primary">{m.sender}: </span>
                <span className="text-foreground">{m.text}</span>
              </div>
            ))}
            <div ref={messagesEndRef} />
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
