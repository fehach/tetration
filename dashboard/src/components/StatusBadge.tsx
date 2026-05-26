interface StatusBadgeProps {
  state: "ok" | "warn" | "error" | "info";
  label: string;
}

const STYLES: Record<StatusBadgeProps["state"], { dot: string; text: string }> = {
  ok: { dot: "bg-cisco-green", text: "text-cisco-green" },
  warn: { dot: "bg-cisco-yellow", text: "text-cisco-yellow" },
  error: { dot: "bg-cisco-red", text: "text-cisco-red" },
  info: { dot: "bg-cisco-blue", text: "text-cisco-blue" },
};

export function StatusBadge({ state, label }: StatusBadgeProps) {
  const style = STYLES[state];
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-surface-secondary/40 px-2.5 py-1 text-xs">
      <span className={`h-2 w-2 rounded-full ${style.dot}`} aria-hidden />
      <span className={style.text}>{label}</span>
    </span>
  );
}
