// Proxy server-side das LEITURAS do backend (achado I-1 da auditoria).
//
// - Exige sessao valida (senao 401).
// - Injeta a READ_API_KEY (server-side; nunca chega ao navegador).
// - Allowlist estrita dos GET permitidos; qualquer outro caminho => 404.
// Assim o backend deixa de ser publico: sem login = sem dados.

import { NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE, verifySessionToken } from "@/lib/session";

export const runtime = "nodejs";

const BACKEND_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STATIC_ALLOWED = new Set([
  "health",
  "opportunities",
  "founder-profile",
  "reports/daily",
  "reports/daily/latest",
  "pipeline/status",
]);

function isAllowedRead(target: string): boolean {
  if (STATIC_ALLOWED.has(target)) return true;
  // GET /opportunities/{id}
  return /^opportunities\/[A-Za-z0-9-]+$/.test(target);
}

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const secret = process.env.SESSION_SECRET ?? "";
  const session = await verifySessionToken(
    req.cookies.get(SESSION_COOKIE)?.value,
    secret,
  );
  if (!session) {
    return NextResponse.json({ detail: "Nao autenticado" }, { status: 401 });
  }

  const { path } = await ctx.params;
  const target = path.join("/");
  if (!isAllowedRead(target)) {
    return NextResponse.json({ detail: "Endpoint nao permitido" }, { status: 404 });
  }

  const key = process.env.READ_API_KEY;
  if (!key) {
    return NextResponse.json(
      { detail: "READ_API_KEY nao configurada no frontend" },
      { status: 503 },
    );
  }

  const qs = req.nextUrl.search; // preserva ?score_min=...&status=...
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/${target}${qs}`, {
      method: "GET",
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
  } catch (err) {
    console.error("data-proxy fetch failed:", err);
    return NextResponse.json(
      { detail: `Nao foi possivel conectar ao backend (${BACKEND_URL})` },
      { status: 502 },
    );
  }

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/json",
    },
  });
}
