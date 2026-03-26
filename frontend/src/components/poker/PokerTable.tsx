import PlayerSeat from "./PlayerSeat";
import Toolbar from "./Toolbar";
import ActionBar from "./ActionBar";
import ChatBubble from "./ChatBubble";
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
}

const PokerTable = ({ table, localPlayerId, holeCards, onMenuOpen, onSitDown, onStartHand }: PokerTableProps) => {
  const players = Object.values(table.players).sort((a, b) => a.seat - b.seat);
  const localPlayer = players.find((p) => p.session_id === localPlayerId) ?? null;

  const board = table.board.primary;
  const pot = table.pot;
  const isAdmin = localPlayerId === table.admin_id;
  const canStart = isAdmin && (table.phase === "waiting" || table.phase === "between_hands");
  const activePlayers = Object.values(table.players).filter(
    (p) => p.status !== "sitting_out" && p.status !== "disconnected"
  );

  return (
    <div className="w-full max-w-[430px] mx-auto h-[100dvh] flex flex-col bg-felt-dark overflow-hidden">
      <Toolbar table={table} onMenuOpen={onMenuOpen} />

      {/* Table area */}
      <div className="flex-1 relative min-h-0">
        {/* Felt oval */}
        <div className="absolute inset-x-4 top-4 bottom-4 rounded-[45%/50%] bg-felt border-4 border-gold-dim/40 shadow-[inset_0_0_60px_rgba(0,0,0,0.4)]" />

        {/* Pot */}
        <div className="absolute top-[38%] left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
          <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Pot</div>
          <div className="text-lg font-bold text-primary">
            {formatAmount(pot, table.rules.denomination)}
          </div>
        </div>

        {/* Community cards */}
        {board.length > 0 && (
          <div className="absolute top-[46%] left-1/2 -translate-x-1/2 -translate-y-1/2 flex gap-1.5">
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
            {/* Ghost placeholders for remaining board cards */}
            {Array.from({ length: 5 - board.length }).map((_, i) => (
              <div
                key={`ghost-${i}`}
                className="w-10 h-14 rounded-lg border border-border/30 opacity-20"
              />
            ))}
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
              position={PORTRAIT_POSITIONS[posIdx] ?? PORTRAIT_POSITIONS[0]}
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
    </div>
  );
};

export default PokerTable;
