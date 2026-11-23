import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface Toast {
  id: number;
  text: string;
  kind: "error" | "info";
}
const Ctx = createContext<(text: string, kind?: Toast["kind"]) => void>(() => undefined);

export const useToast = (): ((text: string, kind?: Toast["kind"]) => void) => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, kind: Toast["kind"] = "error") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, text, kind }]);
    window.setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 6000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div
            key={t.id}
            className={`rise flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-xl ${
              t.kind === "error" ? "border-red-400/50 bg-red-950/90 text-red-100" : "border-cyan-400/40 bg-panel text-slate-100"
            }`}
          >
            <span aria-hidden="true">{t.kind === "error" ? "⚠" : "ℹ"}</span>
            <span className="flex-1">{t.text}</span>
            <button className="opacity-70 hover:opacity-100" aria-label="Dismiss message" onClick={() => setItems((s) => s.filter((x) => x.id !== t.id))}>
              ✕
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
