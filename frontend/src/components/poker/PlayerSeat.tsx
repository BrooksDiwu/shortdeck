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
  position: { top?: string; left?: string };
}

const PlayerSeat = ({ player, isLocal, holeCards, dealerSeat, rules, position }: PlayerSeatProps) => {
  const folded = player.status === "folded";
  const isDealer = player.seat === dealerSeat;
  const cards = isLocal ? holeCards : player.hole_cards;
  const hasCards = cards && cards.length > 0;

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
          {(isLocal ? holeCards : [null, null]).map((card, i) => {
            if (isLocal && card) {
              const label = getCardLabel(card);
              const color = getSuitColor(card.suit);
              return (
                <div
                  key={i}
                  className="w-14 h-20 rounded-lg bg-foreground shadow-lg flex items-center justify-center text-lg font-bold"
                  style={{ color }}
                >
                  {label}
                </div>
              );
            }
            return (
              <div key={i} className="w-4 h-6 rounded text-[6px] bg-chip-red/80 text-foreground flex items-center justify-center font-bold">
                ?
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default PlayerSeat;
