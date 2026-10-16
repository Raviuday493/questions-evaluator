import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="text-sm font-semibold text-brand-600">404</p>
      <h1 className="text-xl font-semibold text-ink">Page not found</h1>
      <p className="text-sm text-ink-muted">The page you are looking for does not exist in the admin console.</p>
      <Link href="/" className="text-sm font-medium text-brand-600 hover:underline">Back to dashboard</Link>
    </main>
  );
}
