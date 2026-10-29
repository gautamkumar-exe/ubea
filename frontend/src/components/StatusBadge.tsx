interface StatusBadgeProps {
  value: string;
  kind?: "severity" | "status" | "generic";
}

export function StatusBadge({ value, kind = "generic" }: StatusBadgeProps) {
  const normalized = value.toLowerCase().replaceAll(" ", "-");
  return <span className={`badge badge--${kind} badge--${normalized}`}>{value.replaceAll("_", " ")}</span>;
}
