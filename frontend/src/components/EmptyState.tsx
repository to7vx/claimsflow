export function EmptyState({
  title,
  message,
  icon,
}: {
  title: string;
  message: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="panel p-10 flex flex-col items-center text-center gap-3">
      {icon && <div className="text-fg-muted">{icon}</div>}
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="max-w-md text-sm text-fg-secondary">{message}</p>
    </div>
  );
}
