import { cn } from "@/lib/utils";
import { getCardLabel, getSuitColor, formatAmount, getChipBreakdown } from "@/utils/gameUtils";
import ChipStack from "@/components/ChipStack";
import type { Player, Card, TableRulesSchema } from "@/types";

const ChipDots = ({ amount }: { amount: number }) => {
  const breakdown = getChipBreakdown(amount).slice(0, 4);
  if (breakdown.length === 0) return null;
  return (
    <div className="flex items-center gap-[2px]">
      {breakdown.map(({ color, count }, i) => (
        <div
          key={i}
          className="rounded-full border border-black/40 flex-shrink-0"
          style={{
            width: 8,
            height: 8,
            background: color,
            boxShadow: count > 1 ? `0 -2px 0 ${color}` : undefined,
          }}
        />
      ))}
    </div>
  );
};

interface PlayerSeatProps {
  player: Player;
  isLocal: boolean;
  holeCards: Card[];
  dealerSeat: number;
  rules: TableRulesSchema;
  phase: string;
  position: { top?: string; left?: string };
  /** Angle in degrees: outward from table center. Bottom=90°, top=270°, right=0°, left=180° */
  seatAngleDeg?: number;
  onRevealCard?: (cardIndex: number) => void;
  pendingSitOut?: boolean;
}

const HAND_PHASES = new Set(["preflop", "flop", "turn", "river", "showdown"]);

/**
 * Derive a simple zone from the outward angle:
 *   "bottom" — local player at bottom (angle ~90°)
 *   "top"    — player at top (angle ~270°)
 *   "left"   — players on left half
 *   "right"  — players on right half
 */
function getZone(angleDeg: number): "bottom" | "top" | "left" | "right" {
  const a = ((angleDeg % 360) + 360) % 360;
  if (a >= 45 && a < 135) return "bottom";
  if (a >= 135 && a < 225) return "left";
  if (a >= 225 && a < 315) return "top";
  return "right";
}

const PlayerSeat = ({
  player, isLocal, holeCards, dealerSeat, rules, phase,
  position, seatAngleDeg = 90, onRevealCard, pendingSitOut,
}: PlayerSeatProps) => {
  const folded = player.status === "folded";
  const isDealer = player.seat === dealerSeat;
  const cards = isLocal ? holeCards : player.hole_cards;
  const isInHand = HAND_PHASES.has(phase) && player.status !== "sitting_out";
  const hasCards = isLocal ? cards.length > 0 : isInHand;
  const zone = getZone(seatAngleDeg);

  const handleCardClick = (i: number) => {
    if (!isLocal || !onRevealCard) return;
    if (player.is_revealed?.[i]) return;
    onRevealCard(i);
  };

  const avatarSize = isLocal ? "w-12 h-12" : "w-10 h-10";

  const avatar = (
    <div
      className={cn(
        "rounded-full flex items-center justify-center text-xs font-bold border-2 relative flex-shrink-0",
        avatarSize,
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
  );

  const nameLabel = (
    <div className="text-[10px] text-foreground font-medium text-center leading-tight max-w-[56px] truncate">
      {player.name}
    </div>
  );

  const chipStackEl = (
    <div className="flex flex-col items-center gap-0.5">
      <ChipStack amount={player.stack} size="sm" />
      <div className="text-[9px] text-primary font-bold whitespace-nowrap">
        {formatAmount(player.stack, rules.denomination)}
      </div>
    </div>
  );

  const betEl = player.current_bet > 0 ? (
    <div className="flex flex-col items-center gap-0.5">
      <ChipDots amount={player.current_bet} />
      <div className="text-[10px] font-bold text-primary bg-secondary/80 rounded-full px-1.5 py-0.5 whitespace-nowrap">
        {formatAmount(player.current_bet, rules.denomination)}
      </div>
    </div>
  ) : null;

  const cardEls = hasCards && !folded ? (
    <div className={cn("flex", isLocal ? "gap-1.5" : "gap-0.5")}>
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
        const otherCard = player.hole_cards?.[i];
        const isRevealed = player.is_revealed?.[i];
        if (isRevealed && otherCard) {
          const label = getCardLabel(otherCard);
          const color = getSuitColor(otherCard.suit);
          return (
            <div key={i} className="w-5 h-7 rounded text-[8px] bg-foreground shadow flex items-center justify-center font-bold" style={{ color }}>
              {label}
            </div>
          );
        }
        return (
          <div
            key={i}
            className="w-5 h-7 rounded bg-red-800 border border-red-400/30 shadow"
            style={{ backgroundImage: "repeating-linear-gradient(45deg, #991b1b 0px, #991b1b 2px, transparent 2px, transparent 6px)" }}
          />
        );
      })}
    </div>
  ) : null;

  // Layout varies by zone:
  //   bottom (local): chip stack to the right of avatar; bet above avatar; cards below avatar
  //   top:   chip stack above; name; avatar; cards below; bet below cards
  //   left:  [chipStack] [avatar + cards-below] [bet to the right toward center]
  //   right: [bet to the left toward center] [avatar + cards-below] [chipStack]

  if (isLocal) {
    // Local player at bottom: bet above, avatar with visual stack to the right,
    // name + stack amount as a label between avatar and cards.
    return (
      <div className="absolute" style={{ ...position, transform: "translate(-50%, -50%)" }}>
        {/* Bet — above the avatar */}
        {betEl && (
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 flex flex-col items-center gap-0.5">
            {betEl}
          </div>
        )}
        <div className="flex flex-col items-center">
          {/* Avatar row with visual chip stack to the right */}
          <div className="relative flex items-center">
            {avatar}
            <div className="absolute left-full ml-2 flex flex-col items-center gap-0.5 pointer-events-none">
              <ChipStack amount={player.stack} size="sm" />
            </div>
          </div>
          {/* Name + stack amount between avatar and cards */}
          <div className="flex flex-col items-center mt-0.5">
            <div className="text-[10px] text-foreground font-medium leading-tight truncate max-w-[80px] text-center">
              {player.name}
            </div>
            <div className="text-[9px] text-primary font-bold">
              {formatAmount(player.stack, rules.denomination)}
            </div>
          </div>
          {/* Cards below */}
          {cardEls && <div className="mt-0.5">{cardEls}</div>}
        </div>
      </div>
    );
  }

  if (zone === "top") {
    // Top players: stack → name → avatar → cards → bet
    return (
      <div className="absolute flex flex-col items-center gap-0.5" style={{ ...position, transform: "translate(-50%, -50%)" }}>
        {chipStackEl}
        {nameLabel}
        {avatar}
        {cardEls && <div className="mt-0.5">{cardEls}</div>}
        {betEl && <div className="mt-0.5">{betEl}</div>}
      </div>
    );
  }

  if (zone === "left") {
    // Left-side players: stack on far left → [name+avatar+cards column] → bet on right (toward center)
    return (
      <div className="absolute flex flex-row items-center gap-1.5" style={{ ...position, transform: "translate(-50%, -50%)" }}>
        <div className="flex-shrink-0">{chipStackEl}</div>
        <div className="flex flex-col items-center gap-0.5">
          {nameLabel}
          {avatar}
          {cardEls && <div className="mt-0.5">{cardEls}</div>}
        </div>
        {betEl && <div className="flex-shrink-0">{betEl}</div>}
      </div>
    );
  }

  // right zone: bet on left (toward center) → [name+avatar+cards column] → stack on far right
  return (
    <div className="absolute flex flex-row items-center gap-1.5" style={{ ...position, transform: "translate(-50%, -50%)" }}>
      {betEl && <div className="flex-shrink-0">{betEl}</div>}
      <div className="flex flex-col items-center gap-0.5">
        {nameLabel}
        {avatar}
        {cardEls && <div className="mt-0.5">{cardEls}</div>}
      </div>
      <div className="flex-shrink-0">{chipStackEl}</div>
    </div>
  );
};

export default PlayerSeat;
