import { useEffect } from "react";

export function EobModal({
  en,
  ar,
  onClose,
}: {
  en: string;
  ar: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="panel max-w-4xl w-full max-h-[80vh] overflow-auto p-6 grid md:grid-cols-2 gap-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
            English EOB
          </h3>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-fg-primary">{en}</p>
        </div>
        <div dir="rtl" lang="ar">
          <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
            بيان الفوائد بالعربية
          </h3>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-fg-primary">{ar}</p>
        </div>
        <button
          className="md:col-span-2 mt-2 text-xs font-mono uppercase tracking-wider text-fg-secondary hover:text-fg-primary transition-colors"
          onClick={onClose}
        >
          Close (Esc)
        </button>
      </div>
    </div>
  );
}
