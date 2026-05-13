/**
 * Tiny pulsing "LIVE" chip. Renders only when the timestamp is within
 * the last 5 minutes — otherwise nothing.
 */
import { parseServerTime } from "@/lib/format";

const LIVE_WINDOW_MS = 5 * 60 * 1000;

export function isLive(iso: string | null | undefined): boolean {
  if (!iso) return false;
  return Date.now() - parseServerTime(iso).getTime() < LIVE_WINDOW_MS;
}

export function LiveBadge({ at, className = "" }: { at: string | null | undefined; className?: string }) {
  if (!isLive(at)) return null;
  return (
    <span className={`inline-flex items-center gap-1 ${className}`} title="Submitted within the last 5 minutes">
      <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse-live" />
      <span className="font-mono text-[9px] uppercase tracking-wider text-accent">live</span>
    </span>
  );
}
