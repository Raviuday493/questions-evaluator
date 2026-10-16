import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500" role="status">
      <Loader2 className="animate-spin text-accent" size={18} />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="qpi-card p-6 flex flex-col items-center text-center gap-3 border-red-200" role="alert">
      <AlertTriangle className="text-red-500" size={28} />
      <p className="text-sm text-slate-700 max-w-md">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-semibold px-4 py-2 rounded-full border border-slate-200 hover:bg-slate-50"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 gap-2">
      <Inbox className="text-slate-300" size={36} strokeWidth={1.6} />
      <p className="font-semibold text-slate-700 text-sm">{title}</p>
      {children && <div className="text-sm text-slate-500 max-w-md">{children}</div>}
    </div>
  );
}
