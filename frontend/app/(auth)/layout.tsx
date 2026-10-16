export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-5 bg-background">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-6 justify-center">
          <div className="w-10 h-10 rounded-xl bg-accent text-white flex items-center justify-center font-bold text-sm shadow-sm">
            QP
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-slate-900">QPI Platform</div>
            <div className="text-[11px] text-slate-500">Question Paper Intel</div>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}
