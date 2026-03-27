import { useState } from "react";
import PlayerSeat from "./PlayerSeat";
import Toolbar from "./Toolbar";
import ActionBar from "./ActionBar";
import ChatBubble from "./ChatBubble";
import Modal from "@/components/Modal";
import { useGameStore } from "@/stores/gameStore";
import { getCardLabel, getSuitColor, formatAmount } from "@/utils/gameUtils";
import type { Table, Card } from "@/types";

// Portrait mobile positions for up to 9 seats.
// Index 0 = local player (bottom center); remaining go counter-clockwise.
const PORTRAIT_POSITIONS: Array<{ top: string; left: string }> = [
  { top: "88%", left: "50%" },  // 0 - local (bottom center)
  { top: "78%", left: "14%" },  // 1
  { top: "60%", left: "6%" },   // 2
  { top: "38%", left: "6%" },   // 3
  { top: "20%", left: "18%" },  // 4
  { top: "10%", left: "50%" },  // 5
  { top: "20%", left: "82%" },  // 6
  { top: "38%", left: "94%" },  // 7
  { top: "60%", left: "94%" },  // 8
];

interface PokerTableProps {
  table: Table;
  localPlayerId: string | null;
  holeCards: Card[];
  onMenuOpen: () => void;
  onSitDown: (seat: number) => void;
  onStartHand: () => void;
  pendingSitOut: boolean;
}

const PokerTable = ({ table, localPlayerId, holeCards, onMenuOpen, onSitDown, onStartHand, pendingSitOut }: PokerTableProps) => {
  const sendMessage = useGameStore((s) => s.sendMessage);
  const rabbitHuntCards = useGameStore((s) => s.rabbitHuntCards);
  const clearRabbitHunt = useGameStore((s) => s.clearRabbitHunt);
  const [confirmRevealIndex, setConfirmRevealIndex] = useState<number | null>(null);

  const players = Object.values(table.players).sort((a, b) => a.seat - b.seat);
  const localPlayer = players.find((p) => p.session_id === localPlayerId) ?? null;

  const board = table.board.primary;
  const secondaryBoard = table.board.secondary;
  const hasDoubleBoard = table.rules.extra_flop && secondaryBoard.length > 0;
  const pot = table.pot;
  const isSeated = localPlayer !== null;
  const canStart = isSeated && (table.phase === "waiting" || table.phase === "between_hands");
  const activePlayers = Object.values(table.players).filter(
    (p) => p.status !== "sitting_out" && p.status !== "disconnected"
  );

  // Rabbit hunt is available when hand is over and fewer than 5 community cards were dealt
  const canRabbitHunt = isSeated &&
    (table.phase === "showdown" || table.phase === "between_hands") &&
    board.length < 5 &&
    rabbitHuntCards.length === 0;  // hide button once cards are fetched

  const handleRabbitHunt = () => {
    sendMessage({ type: "rabbit_hunt_request" });
  };


  const handleRevealCard = (cardIndex: number) => {
    setConfirmRevealIndex(cardIndex);
  };

  const handleConfirmReveal = () => {
    if (confirmRevealIndex !== null) {
      sendMessage({ type: "reveal_card", card_index: confirmRevealIndex as 0 | 1 });
    }
    setConfirmRevealIndex(null);
  };

  return (
    <div className="w-full max-w-[430px] mx-auto h-[100dvh] flex flex-col bg-felt-dark overflow-hidden">
      <Toolbar table={table} onMenuOpen={onMenuOpen} />

      {/* Table area */}
      <div className="flex-1 relative min-h-0">
        {/* Felt oval */}
        <div className="absolute inset-x-4 top-4 bottom-4 rounded-[45%/50%] bg-felt border-4 border-gold-dim/40 shadow-[inset_0_0_60px_rgba(0,0,0,0.4)]" />

        {/* Pot */}
        <div className={`absolute ${hasDoubleBoard ? "top-[24%]" : "top-[38%]"} left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center`}>
          <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Pot</div>
          <div className="text-lg font-bold text-primary">
            {formatAmount(pot, table.rules.denomination)}
          </div>
        </div>

        {/* Community cards */}
        {board.length > 0 && (
          <div className={`absolute ${hasDoubleBoard ? "top-[43%]" : "top-[46%]"} left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-1.5`}>
            {/* Board label when double boards are active */}
            {hasDoubleBoard && (
              <div className="text-[9px] text-amber-400/70 uppercase tracking-widest font-semibold">Board 1</div>
            )}
            <div className="flex gap-1.5">
              {board.map((card, i) => {
                const label = getCardLabel(card);
                const color = getSuitColor(card.suit);
                return (
                  <div
                    key={i}
                    className="w-10 h-14 rounded-lg bg-foreground shadow-xl flex items-center justify-center text-sm font-bold"
                    style={{ color }}
                  >
                    {label}
                  </div>
                );
              })}
              {/* Remaining slots: show rabbit hunt cards or ghost placeholders */}
              {Array.from({ length: 5 - board.length }).map((_, i) => {
                const rabbitCard = rabbitHuntCards[i];
                if (rabbitCard) {
                  const label = getCardLabel(rabbitCard);
                  const color = getSuitColor(rabbitCard.suit);
                  return (
                    <div
                      key={`rabbit-${i}`}
                      className="w-10 h-14 rounded-lg bg-foreground/60 shadow-xl flex items-center justify-center text-sm font-bold ring-2 ring-amber-400/70"
                      style={{ color }}
                    >
                      {label}
                    </div>
                  );
                }
                return (
                  <div
                    key={`ghost-${i}`}
                    className="w-10 h-14 rounded-lg border border-border/30 opacity-20"
                  />
                );
              })}
            </div>

            {/* Secondary board (double board mode) */}
            {hasDoubleBoard && (
              <>
                <div className="text-[9px] text-amber-400/70 uppercase tracking-widest font-semibold mt-0.5">Board 2</div>
                <div className="flex gap-1.5">
                  {secondaryBoard.map((card, i) => {
                    const label = getCardLabel(card);
                    const color = getSuitColor(card.suit);
                    return (
                      <div
                        key={i}
                        className="w-10 h-14 rounded-lg bg-foreground shadow-xl flex items-center justify-center text-sm font-bold ring-1 ring-amber-400/40"
                        style={{ color }}
                      >
                        {label}
                      </div>
                    );
                  })}
                  {/* Ghost placeholders for remaining secondary board slots */}
                  {Array.from({ length: 5 - secondaryBoard.length }).map((_, i) => (
                    <div
                      key={`ghost-secondary-${i}`}
                      className="w-10 h-14 rounded-lg border border-border/30 opacity-20"
                    />
                  ))}
                </div>
              </>
            )}

            {/* Rabbit hunt button / dismiss */}
            {canRabbitHunt && (
              <button
                onClick={handleRabbitHunt}
                className="mt-1 px-3 py-1 rounded-full bg-amber-600/80 text-white text-[10px] font-semibold hover:bg-amber-500 active:scale-95 transition-all shadow"
              >
                🐇 Rabbit Hunt
              </button>
            )}
            {rabbitHuntCards.length > 0 && (
              <button
                onClick={clearRabbitHunt}
                className="mt-1 px-3 py-1 rounded-full bg-zinc-700/80 text-zinc-300 text-[10px] font-semibold hover:bg-zinc-600 active:scale-95 transition-all shadow"
              >
                Hide
              </button>
            )}
          </div>
        )}

        {/* Start Game button — admin only, when not in a hand */}
        {canStart && (
          <div className="absolute top-[54%] left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-1">
            <button
              onClick={onStartHand}
              disabled={activePlayers.length < 2}
              className="px-6 py-2.5 rounded-full bg-primary text-primary-foreground font-semibold text-sm shadow-lg hover:bg-primary/90 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {table.phase === "waiting" ? "Start Game" : "Deal Next Hand"}
            </button>
            {activePlayers.length < 2 && (
              <span className="text-[10px] text-muted-foreground">Need 2+ players</span>
            )}
          </div>
        )}

        {/* Player seats — positioned by relative seat index so empty seats don't overlap */}
        {players.map((player) => {
          const localSeat = localPlayer?.seat ?? 0;
          const relIdx = (player.seat - localSeat + table.rules.max_players) % table.rules.max_players;
          const posIdx = relIdx < PORTRAIT_POSITIONS.length ? relIdx : 0;
          return (
            <PlayerSeat
              key={player.session_id}
              player={player}
              isLocal={player.session_id === localPlayerId}
              holeCards={player.session_id === localPlayerId ? holeCards : []}
              dealerSeat={table.dealer_seat}
              rules={table.rules}
              phase={table.phase}
              position={PORTRAIT_POSITIONS[posIdx] ?? PORTRAIT_POSITIONS[0]}
              onRevealCard={player.session_id === localPlayerId ? handleRevealCard : undefined}
              pendingSitOut={player.session_id === localPlayerId ? pendingSitOut : false}
            />
          );
        })}

        {/* Empty seat prompts */}
        {(() => {
          const takenSeats = new Set(players.map((p) => p.seat));
          const localSeat = localPlayer?.seat ?? 0;
          return Array.from({ length: table.rules.max_players }, (_, seat) => {
            if (takenSeats.has(seat)) return null;
            const relIdx = (seat - localSeat + table.rules.max_players) % table.rules.max_players;
            const posIdx = relIdx < PORTRAIT_POSITIONS.length ? relIdx : 0;
            return (
              <button
                key={`empty-${seat}`}
                onClick={() => localPlayer === null ? onSitDown(seat) : undefined}
                disabled={localPlayer !== null}
                className="absolute flex items-center justify-center w-10 h-10 rounded-full border-2 border-dashed border-border/50 text-muted-foreground text-[10px] font-medium hover:border-primary hover:text-primary transition-colors disabled:cursor-default disabled:pointer-events-none"
                style={{ ...PORTRAIT_POSITIONS[posIdx], transform: "translate(-50%, -50%)" }}
              >
                {localPlayer === null ? "SIT" : ""}
              </button>
            );
          });
        })()}

        <ChatBubble />
      </div>

      {/* Action bar — only shown when it's the local player's turn */}
      {localPlayer && (
        <ActionBar table={table} localPlayer={localPlayer} />
      )}

      {/* Reveal card confirmation — rendered here (outside transformed elements) so fixed positioning works */}
      <Modal
        open={confirmRevealIndex !== null}
        onClose={() => setConfirmRevealIndex(null)}
        title="Show Card?"
        showClose
      >
        <p className="text-sm text-zinc-300 mb-4">
          Show card {confirmRevealIndex === 0 ? "1" : "2"} to all players? This cannot be undone.
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => setConfirmRevealIndex(null)}
            className="flex-1 py-2 rounded-lg text-sm font-semibold bg-zinc-700 text-zinc-200 hover:bg-zinc-600 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirmReveal}
            className="flex-1 py-2 rounded-lg text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Show Card
          </button>
        </div>
      </Modal>

    </div>
  );
};

export default PokerTable;
