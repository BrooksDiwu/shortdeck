import { Settings, Volume2, VolumeX, Menu } from "lucide-react";
import { useSoundStore } from "@/stores/soundStore";
import { getGameModeLabel, formatBlinds } from "@/utils/gameUtils";
import type { Table } from "@/types";

interface ToolbarProps {
  table: Table | null;
  onMenuOpen: () => void;
}

const Toolbar = ({ table, onMenuOpen }: ToolbarProps) => {
  const { muted, toggleMute } = useSoundStore();

  return (
    <div className="flex items-center justify-between px-3 py-2 bg-felt-dark/80 border-b border-border">
      <div className="flex items-center gap-2">
        <button onClick={onMenuOpen} aria-label="Open menu">
          <Menu className="w-5 h-5 text-muted-foreground" />
        </button>
        <span className="text-sm font-bold text-primary tracking-wide">POKER</span>
      </div>
      <div className="text-[11px] text-muted-foreground font-medium">
        {table ? `${getGameModeLabel(table.rules)} · ${formatBlinds(table.rules)}` : "Loading..."}
      </div>
      <div className="flex items-center gap-3">
        <button onClick={toggleMute} aria-label={muted ? "Unmute" : "Mute"}>
          {muted
            ? <VolumeX className="w-4 h-4 text-muted-foreground" />
            : <Volume2 className="w-4 h-4 text-muted-foreground" />
          }
        </button>
        <button onClick={onMenuOpen} aria-label="Settings">
          <Settings className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
    </div>
  );
};

export default Toolbar;
