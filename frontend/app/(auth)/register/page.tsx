"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api, errorText } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const departments = useQuery({ queryKey: ["departments"], queryFn: api.departments });
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "", department_code: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (form.password !== form.confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      const user = await api.register({
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        password: form.password,
        department_code: form.department_code || null,
      });
      queryClient.setQueryData(["me"], user);
      router.replace("/upload");
      router.refresh();
    } catch (err) {
      setError(errorText(err));
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="qpi-card p-6 flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Create your faculty account</h1>
        <p className="text-sm text-slate-500 mt-1">Upload drafts and prepare better next papers.</p>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-3 py-2" role="alert">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label className="qpi-label" htmlFor="full-name">Full name</label>
        <input id="full-name" required minLength={2} autoComplete="name" value={form.full_name}
          onChange={set("full_name")} className="qpi-input" />
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="qpi-label" htmlFor="email">Email</label>
        <input id="email" type="email" required autoComplete="email" value={form.email}
          onChange={set("email")} className="qpi-input" />
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="qpi-label" htmlFor="department">Department</label>
        <select id="department" value={form.department_code} onChange={set("department_code")} className="qpi-input"
          disabled={departments.isLoading}>
          <option value="">{departments.isLoading ? "Loading departments..." : "Select your department"}</option>
          {departments.data?.map((d) => (
            <option key={d.code} value={d.code}>{d.name}</option>
          ))}
        </select>
        {departments.isError && <span className="text-xs text-red-600">Could not load departments.</span>}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="qpi-label" htmlFor="password">Password</label>
          <input id="password" type="password" required minLength={8} maxLength={72} autoComplete="new-password"
            value={form.password} onChange={set("password")} className="qpi-input" />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="qpi-label" htmlFor="confirm">Confirm password</label>
          <input id="confirm" type="password" required minLength={8} maxLength={72} autoComplete="new-password"
            value={form.confirm} onChange={set("confirm")} className="qpi-input" />
        </div>
      </div>
      <p className="text-xs text-slate-500 -mt-2">At least 8 characters, including a letter and a digit.</p>

      <button type="submit" disabled={submitting}
        className="bg-accent text-white font-semibold text-sm py-2.5 rounded-full hover:bg-primary transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
        {submitting && <Loader2 className="animate-spin" size={16} />}
        Create account
      </button>

      <p className="text-sm text-slate-500 text-center">
        Already registered?{" "}
        <Link href="/login" className="text-accent font-semibold hover:underline">Sign in</Link>
      </p>
    </form>
  );
}
