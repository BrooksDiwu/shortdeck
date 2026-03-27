import { cn } from "@/lib/utils";
import { getCardLabel, getSuitColor } from "@/utils/gameUtils";
import { formatAmount } from "@/utils/gameUtils";
import type { Player, Card, TableRulesSchema } from "@/types";

interface PlayerSeatProps {
  player: Player;
  isLocal: boolean;
  holeCards: Card[];
  dealerSeat: number;
  rules: TableRulesSchema;
  phase: string;
  position: { top?: string; left?: string };
  onRevealCard?: (cardIndex: number) => void;
  pendingSitOut?: boolean;
}

const HAND_PHASES = new Set(["preflop", "flop", "turn", "river", "showdown"]);

const PlayerSeat = ({ player, isLocal, holeCards, dealerSeat, rules, phase, position, onRevealCard, pendingSitOut }: PlayerSeatProps) => {
  const folded = player.status === "folded";
  const isDealer = player.seat === dealerSeat;
  // For local player use dealt holeCards; for others use server-sent hole_cards (populated at showdown/reveal)
  const cards = isLocal ? holeCards : player.hole_cards;
  const isInHand = HAND_PHASES.has(phase) && player.status !== "sitting_out";
  // Show card area if local player has cards, or if other player is in an active hand (show backs)
  const hasCards = isLocal ? cards.length > 0 : isInHand;

  const handleCardClick = (i: number) => {
    if (!isLocal || !onRevealCard) return;
    if (player.is_revealed?.[i]) return; // already revealed
    onRevealCard(i);
  };

  return (
    <div
      className="absolute flex flex-col items-center"
      style={{ ...position, transform: "translate(-50%, -50%)" }}
    >
      {/* Bet indicator */}
      {player.current_bet > 0 && (
        <div className="absolute -top-5 text-[10px] font-bold text-primary bg-secondary/80 rounded-full px-1.5 py-0.5">
          {formatAmount(player.current_bet, rules.denomination)}
        </div>
      )}

      {/* Avatar */}
      <div
        className={cn(
          "rounded-full flex items-center justify-center text-xs font-bold border-2 relative",
          isLocal ? "w-12 h-12" : "w-10 h-10",
          folded ? "bg-muted border-muted-foreground/30 opacity-50" : "bg-secondary border-border",
          isLocal && "border-primary",
          player.status === "disconnected" && "opacity-40"
        )}
      >
        <span className="text-foreground">{player.name.slice(0, 2).toUpperCase()}</span>
        {isDealer && (
          <span className="absolute -top-1 -right-1 bg-primary text-primary-foreground text-[8px] w-4 h-4 rounded-full flex items-center justify-center font-bold">
            D
          </span>
        )}
        {player.status === "all_in" && (
          <span className="absolute -bottom-1 -right-1 bg-accent text-accent-foreground text-[7px] rounded-full px-1 font-bold">
            AI
          </span>
        )}
        {(player.status === "sitting_out" || pendingSitOut) && (
          <span className="absolute -bottom-1 -left-1 bg-zinc-600 text-zinc-200 text-[7px] rounded-full px-1 font-bold whitespace-nowrap">
            {pendingSitOut && player.status !== "sitting_out" ? "OUT↓" : "OUT"}
          </span>
        )}
      </div>

      {/* Name & stack */}
      <div className="text-[10px] text-foreground font-medium mt-0.5 text-center leading-tight max-w-[64px] truncate">
        {player.name}
      </div>
      <div className="text-[9px] text-primary font-bold">
        {formatAmount(player.stack, rules.denomination)}
      </div>

      {/* Cards */}
      {hasCards && !folded && (
        <div className={cn("flex mt-0.5", isLocal ? "gap-1.5" : "gap-0.5")}>
          {Array.from({ length: rules.hole_cards_count }).map((_, i) => {
            if (isLocal) {
              const card = holeCards[i];
              if (!card) return null;
              const label = getCardLabel(card);
              const color = getSuitColor(card.suit);
              const alreadyRevealed = player.is_revealed?.[i];
              const canReveal = !!onRevealCard && !alreadyRevealed;
              return (
                <div
                  key={i}
                  onClick={() => handleCardClick(i)}
                  className={cn(
                    "w-14 h-20 rounded-lg bg-foreground shadow-lg flex items-center justify-center text-lg font-bold relative",
                    canReveal && "cursor-pointer hover:ring-2 hover:ring-primary active:scale-95 transition-transform"
                  )}
                  style={{ color }}
                >
                  {label}
                  {alreadyRevealed && (
                    <span className="absolute top-0.5 right-0.5 text-[7px] text-primary font-bold leading-none">
                      SHOWN
                    </span>
                  )}
                </div>
              );
            }

            // Other players
            const otherCard = player.hole_cards?.[i];
            const isRevealed = player.is_revealed?.[i];
            if (isRevealed && otherCard) {
              // Voluntarily revealed or showdown — show face
              const label = getCardLabel(otherCard);
              const color = getSuitColor(otherCard.suit);
              return (
                <div
                  key={i}
                  className="w-5 h-7 rounded text-[8px] bg-foreground shadow flex items-center justify-center font-bold"
                  style={{ color }}
                >
                  {label}
                </div>
              );
            }
            // Face-down card back
            return (
              <div
                key={i}
                className="w-5 h-7 rounded bg-blue-900 border border-blue-400/30 shadow flex items-center justify-center"
                style={{
                  backgroundImage: "repeating-linear-gradient(45deg, #1e3a8a 0px, #1e3a8a 2px, transparent 2px, transparent 6px)",
                }}
              />
            );
          })}
        </div>
      )}

    </div>
  );
};

export default PlayerSeat;
