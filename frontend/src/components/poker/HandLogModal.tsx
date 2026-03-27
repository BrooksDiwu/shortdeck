import Modal from "@/components/Modal";
import { formatAmount } from "@/utils/gameUtils";
import type { Table } from "@/types";

interface HandLogModalProps {
  open: boolean;
  onClose: () => void;
  entries: Table["hand_log"];
  denomination: Table["rules"]["denomination"];
}

export default function HandLogModal({ open, onClose, entries, denomination }: HandLogModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Hand Log" className="max-w-2xl">
      {entries.length === 0 ? (
        <p className="text-sm text-zinc-400">Completed hands will appear here once the table has played a hand.</p>
      ) : (
        <div className="max-h-[70vh] overflow-y-auto space-y-4 pr-1">
          {entries.map((entry) => (
            <section
              key={`${entry.hand_number}-${entry.completed_at}`}
              className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-white font-semibold">Hand #{entry.hand_number}</div>
                  <div className="text-xs text-zinc-500">
                    {new Date(entry.completed_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                  </div>
                </div>
                <div className="text-sm font-semibold text-emerald-300">
                  Pot {formatAmount(entry.pot, denomination)}
                </div>
              </div>

              <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2">
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500 mb-2">
                  Hand History
                </div>
                <div className="space-y-1 font-mono text-xs text-zinc-300">
                  {entry.action_lines.map((line, index) => (
                    <div key={`${entry.hand_number}-line-${index}`}>{line}</div>
                  ))}
                </div>
              </div>
            </section>
          ))}
        </div>
      )}
    </Modal>
  );
}
