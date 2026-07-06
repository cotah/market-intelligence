// Proxy server-side dos endpoints de CONTROLE do backend.
//
// A chave CONTROL_API_KEY fica apenas no servidor Next.js (sem NEXT_PUBLIC)
// e e injetada aqui via header X-API-Key — nunca chega ao navegador.
// Apenas os endpoints da allowlist abaixo podem passar; qualquer outro
// caminho recebe 404.

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Allowlist: metodo + caminho exatos dos 5 endpoints de controle.
const ALLOWED: Record<string, Set<string>> = {
  POST: new Set([
    "pipeline/start",
    "pipeline/stop",
    "pipeline/run-once",
    "reports/daily/generate",
  ]),
  PUT: new Set(["founder-profile"]),
};

async function proxy(
  req: NextRequest,
  params: Promise<{ path: string[] }>,
): Promise<NextResponse> {
  const { path } = await params;
  const target = path.join("/");

  if (!ALLOWED[req.method]?.has(target)) {
    return NextResponse.json({ detail: "Endpoint nao permitido" }, { status: 404 });
  }

  const key = process.env.CONTROL_API_KEY;
  if (!key) {
    // Fail closed: sem chave configurada, controle desligado (mesmo contrato do backend).
    return NextResponse.json(
      { detail: "CONTROL_API_KEY nao configurada no frontend" },
      { status: 503 },
    );
  }

  const body = await req.text();
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/${target}`, {
      method: req.method,
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      body: body || undefined,
      cache: "no-store",
    });
  } catch (err) {
    // Log server-side para diagnostico (nunca inclui a chave).
    console.error("control-proxy fetch failed:", err);
    const cause =
      err instanceof Error ? (err.cause ?? err.message) : String(err);
    return NextResponse.json(
      { detail: `Nao foi possivel conectar ao backend (${BACKEND_URL}): ${cause}` },
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

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return proxy(req, ctx.params);
}

export async function PUT(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return proxy(req, ctx.params);
}
