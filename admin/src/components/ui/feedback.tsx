"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Inbox, Lock, RefreshCw, X, XCircle } from "lucide-react";
import { ApiError, errorText } from "@/api/client";
import { cn } from "@/utils/format";
import { Button, Input } from "./primitives";

// ------------------------------------------------------------------ toasts
type ToastKind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

const ToastContext = createContext<{ notify: (kind: ToastKind, message: string) => void } | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const dismiss = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), []);
  const notify = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId.current++;
      setItems((all) => [...all.slice(-3), { id, kind, message }]);
      setTimeout(() => dismiss(id), kind === "error" ? 7000 : 4000);
    },
    [dismiss],
  );
  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
        {items.map((t) => (
          <div
            key={t.id}
            role={t.kind === "error" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex items-start gap-2 rounded-lg border bg-white px-3 py-2.5 text-sm shadow-lg",
              t.kind === "error" ? "border-red-200" : t.kind === "success" ? "border-emerald-200" : "border-line",
            )}
          >
            {t.kind === "error" ? <XCircle size={18} className="mt-0.5 shrink-0 text-red-600" /> : <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-600" />}
            <p className="flex-1 text-ink">{t.message}</p>
            <button type="button" aria-label="Dismiss notification" onClick={() => dismiss(t.id)} className="text-ink-faint hover:text-ink">
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return {
    success: (m: string) => ctx.notify("success", m),
    error: (e: unknown, fallback?: string) => ctx.notify("error", fallback ? `${fallback}: ${errorText(e)}` : errorText(e)),
    info: (m: string) => ctx.notify("info", m),
  };
}

// ------------------------------------------------------------------ modal
export function Modal({ open, onClose, title, children, footer, size = "md" }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg";
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const first = panel.current?.querySelector<HTMLElement>("input, select, textarea, button:not([aria-label='Close dialog'])");
    first?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 pt-[10vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={panel} role="dialog" aria-modal="true" aria-label={title} className={cn("w-full rounded-lg bg-white shadow-xl", size === "lg" ? "max-w-2xl" : "max-w-md")}>
        <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          <button type="button" aria-label="Close dialog" onClick={onClose} className="rounded p-1 text-ink-faint hover:bg-slate-100 hover:text-ink">
            <X size={18} />
          </button>
        </header>
        <div className="px-5 py-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-line bg-slate-50 px-5 py-3 rounded-b-lg">{footer}</footer>}
      </div>
    </div>
  );
}

export interface ConfirmOptions {
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  /** Require typing this text to enable the confirm button (very destructive actions). */
  typeToConfirm?: string;
  /** Show a free-text reason field; its value is passed to onConfirm. */
  reasonLabel?: string;
}

export function ConfirmDialog({ open, options, onCancel, onConfirm, busy }: {
  open: boolean;
  options: ConfirmOptions | null;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
  busy?: boolean;
}) {
  const [typed, setTyped] = useState("");
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (open) {
      setTyped("");
      setReason("");
    }
  }, [open]);
  if (!options) return null;
  const blocked = Boolean(options.typeToConfirm) && typed.trim() !== options.typeToConfirm;
  return (
    <Modal
      open={open}
      onClose={busy ? () => undefined : onCancel}
      title={options.title}
      footer={
        <>
          <Button onClick={onCancel} disabled={busy}>Cancel</Button>
          <Button variant={options.danger ? "danger" : "primary"} loading={busy} disabled={blocked} onClick={() => onConfirm(reason)}>
            {options.confirmLabel ?? "Confirm"}
          </Button>
        </>
      }
    >
      <div className="flex gap-3">
        {options.danger && <AlertTriangle className="mt-0.5 shrink-0 text-red-600" size={20} aria-hidden />}
        <div className="space-y-3 text-sm text-ink-soft">
          <div>{options.message}</div>
          {options.reasonLabel && (
            <label className="block">
              <span className="text-xs font-medium text-ink-soft">{options.reasonLabel}</span>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} className="mt-1" placeholder="Optional" />
            </label>
          )}
          {options.typeToConfirm && (
            <label className="block">
              <span className="text-xs font-medium text-ink-soft">
                Type <code className="rounded bg-slate-100 px-1 font-mono text-ink">{options.typeToConfirm}</code> to confirm
              </span>
              <Input value={typed} onChange={(e) => setTyped(e.target.value)} className="mt-1" autoComplete="off" />
            </label>
          )}
        </div>
      </div>
    </Modal>
  );
}

/** Promise-free confirm helper: `ask({...}, async (reason) => {...})`. */
export function useConfirm() {
  const [state, setState] = useState<{ options: ConfirmOptions; action: (reason: string) => Promise<unknown> } | null>(null);
  const [busy, setBusy] = useState(false);
  const ask = useCallback((options: ConfirmOptions, action: (reason: string) => Promise<unknown>) => setState({ options, action }), []);
  const dialog = (
    <ConfirmDialog
      open={state !== null}
      options={state?.options ?? null}
      busy={busy}
      onCancel={() => setState(null)}
      onConfirm={async (reason) => {
        if (!state) return;
        setBusy(true);
        try {
          await state.action(reason);
          setState(null);
        } catch {
          // the action reports its own error; keep the dialog open for a retry
        } finally {
          setBusy(false);
        }
      }}
    />
  );
  return { ask, dialog };
}

// ------------------------------------------------------------------ states
export function EmptyState({ title, message, action }: { title: string; message?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <Inbox className="text-ink-faint" size={28} aria-hidden />
      <p className="text-sm font-medium text-ink">{title}</p>
      {message && <p className="max-w-sm text-sm text-ink-muted">{message}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const status = error instanceof ApiError ? error.status : undefined;
  if (status === 403) {
    return (
      <div className={cn("flex flex-col items-center gap-2 text-center", compact ? "py-6" : "py-12")}>
        <Lock className="text-ink-faint" size={26} aria-hidden />
        <p className="text-sm font-medium text-ink">You don&apos;t have access to this</p>
        <p className="max-w-sm text-sm text-ink-muted">{errorText(error)}</p>
      </div>
    );
  }
  return (
    <div className={cn("flex flex-col items-center gap-2 text-center", compact ? "py-6" : "py-12")} role="alert">
      <XCircle className="text-red-500" size={26} aria-hidden />
      <p className="text-sm font-medium text-ink">{status === 404 ? "Not found" : "Couldn't load this data"}</p>
      <p className="max-w-md text-sm text-ink-muted">{errorText(error)}</p>
      {onRetry && status !== 404 && (
        <Button size="sm" onClick={onRetry} icon={<RefreshCw size={14} />}>
          Retry
        </Button>
      )}
    </div>
  );
}
