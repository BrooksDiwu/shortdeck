import { useState, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useGameStore } from "@/stores/gameStore";
import { formatAmount } from "@/utils/gameUtils";
import type { Table, Player } from "@/types";

interface ActionBarProps {
  table: Table;
  localPlayer: Player;
}

function computeCallAmount(table: Table, player: Player): number {
  const maxBet = Math.max(...Object.values(table.players).map((p) => p.current_bet));
  return Math.max(0, maxBet - player.current_bet);
}

function computeMinRaise(table: Table): number {
  const maxBet = Math.max(...Object.values(table.players).map((p) => p.current_bet));
  return maxBet + table.rules.big_blind;
}

function computePotLimit(table: Table, player: Player): number {
  const callAmount = computeCallAmount(table, player);
  const potAfterCall = table.pot + callAmount;
  return callAmount + potAfterCall;
}

function computeMaxRaise(table: Table, player: Player): number {
  if (table.rules.betting === "pot_limit") {
    return Math.min(player.stack + player.current_bet, computePotLimit(table, player));
  }
  return player.stack + player.current_bet;
}

const ActionBar = ({ table, localPlayer }: ActionBarProps) => {
  const sendMessage = useGameStore((s) => s.sendMessage);
  const [raiseAmount, setRaiseAmount] = useState(0);

  const callAmount = computeCallAmount(table, localPlayer);
  const canCheck = callAmount === 0;
  const minRaise = computeMinRaise(table);
  const maxRaise = computeMaxRaise(table, localPlayer);
  const potLimit = computePotLimit(table, localPlayer);
  const isAllIn = localPlayer.stack <= callAmount;

  useEffect(() => {
    setRaiseAmount(minRaise);
  }, [minRaise]);

  const currentRaise = Math.max(minRaise, Math.min(raiseAmount || minRaise, maxRaise));
  const denom = table.rules.denomination;

  const handleAction = useCallback(
    (action: "fold" | "check" | "call" | "raise" | "all_in", amount?: number) => {
      console.log('[ActionBar] handleAction:', action, amount);
      sendMessage({ type: "action", action, amount });
    },
    [sendMessage]
  );

  const isActing = table.current_action_seat === localPlayer.seat;
  const isHandActive = ["preflop", "flop", "turn", "river"].includes(table.phase);

  console.log('[ActionBar] isActing:', isActing, 'isHandActive:', isHandActive, 'current_action_seat:', table.current_action_seat, 'localSeat:', localPlayer.seat, 'phase:', table.phase);

  if (!isActing || !isHandActive) return null;

  return (
    <div className="bg-felt-dark/90 border-t border-border px-3 py-2 space-y-2">
      {/* Quick-select presets */}
      <div className="flex gap-1">
        {[
          { label: "Min", value: minRaise },
          { label: "½ Pot", value: Math.floor(potLimit / 2) },
          { label: "Pot", value: potLimit },
          { label: "All-in", value: maxRaise },
        ].map(({ label, value }) => (
          <button
            key={label}
            onClick={() => setRaiseAmount(value)}
            className={cn(
              "flex-1 py-1.5 rounded-lg text-[11px] font-semibold transition-colors active:scale-95",
              currentRaise === value
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Bet slider */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground w-10 shrink-0">
          {formatAmount(minRaise, denom)}
        </span>
        <input
          type="range"
          min={minRaise}
          max={maxRaise}
          step={table.rules.big_blind}
          value={currentRaise}
          onChange={(e) => setRaiseAmount(Number(e.target.value))}
          className="flex-1 h-1 accent-primary"
        />
        <span className="text-[10px] text-muted-foreground w-10 shrink-0 text-right">
          {formatAmount(maxRaise, denom)}
        </span>
        <span className="text-xs font-bold text-primary min-w-[48px] text-right">
          {formatAmount(currentRaise, denom)}
        </span>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => handleAction("fold")}
          className={cn(
            "flex-1 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all active:scale-95",
            "bg-destructive text-destructive-foreground"
          )}
        >
          Fold
        </button>
        <button
          onClick={() => handleAction(canCheck ? "check" : "call")}
          className={cn(
            "flex-1 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all active:scale-95",
            "bg-secondary text-secondary-foreground border border-border"
          )}
        >
          {canCheck ? "Check" : `Call ${formatAmount(callAmount, denom)}`}
        </button>
        <button
          onClick={() => isAllIn ? handleAction("all_in") : handleAction("raise", currentRaise)}
          className={cn(
            "flex-1 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all active:scale-95",
            "bg-primary text-primary-foreground"
          )}
        >
          {isAllIn ? "All-In" : `Bet ${formatAmount(currentRaise, denom)}`}
        </button>
      </div>
    </div>
  );
};

export default ActionBar;
