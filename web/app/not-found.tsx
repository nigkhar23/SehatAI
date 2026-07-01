import Link from "next/link";

export default function NotFound() {
  return (
    <main className="relative z-[2] flex min-h-screen flex-col items-center justify-center px-5 text-center">
      <div className="font-mono text-sm uppercase tracking-[0.3em] text-ink-faint">404</div>
      <h1 className="mt-3 font-display text-3xl text-ink">No card here.</h1>
      <Link
        href="/"
        className="mt-6 rounded-lg bg-forest px-5 py-2.5 text-sm font-medium text-paper"
      >
        Back to Sehat
      </Link>
    </main>
  );
}
