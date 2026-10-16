"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api, errorText } from "@/lib/api";

function safeNext(next: string | null): string {
  // Only allow same-site relative paths to avoid open redirects.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/upload";
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await api.login(email.trim(), password);
      queryClient.setQueryData(["me"], user);
      router.replace(safeNext(params.get("next")));
      router.refresh();
    } catch (err) {
      setError(errorText(err));
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="qpi-card p-6 flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Sign in</h1>
        <p className="text-sm text-slate-500 mt-1">Access your question paper analyses.</p>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-3 py-2" role="alert">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label className="qpi-label" htmlFor="email">Email</label>
        <input id="email" type="email" required autoComplete="email" value={email}
          onChange={(e) => setEmail(e.target.value)} className="qpi-input" />
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="qpi-label" htmlFor="password">Password</label>
        <input id="password" type="password" required autoComplete="current-password" value={password}
          onChange={(e) => setPassword(e.target.value)} className="qpi-input" />
      </div>

      <button type="submit" disabled={submitting}
        className="bg-accent text-white font-semibold text-sm py-2.5 rounded-full hover:bg-primary transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
        {submitting && <Loader2 className="animate-spin" size={16} />}
        Sign in
      </button>

      <p className="text-sm text-slate-500 text-center">
        New to QPI?{" "}
        <Link href="/register" className="text-accent font-semibold hover:underline">Create an account</Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
