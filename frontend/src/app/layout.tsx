import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Market Intelligence AI",
  description: "Pipeline de 11 agentes que cacam oportunidades de negocio.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen antialiased">
        <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-lg font-semibold tracking-tight text-zinc-100">
                Market Intelligence
              </span>
              <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-400">
                AI
              </span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <NavLink href="/" label="Dashboard" />
              <NavLink href="/reports" label="Relatorios" />
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="rounded-md px-3 py-1.5 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
    >
      {label}
    </Link>
  );
}
