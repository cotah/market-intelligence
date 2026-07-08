// Encerra a sessao limpando o cookie. GET redireciona para /login (link "Sair");
// POST responde JSON (para chamadas via fetch).

import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/session";

export const runtime = "nodejs";

function clear(res: NextResponse): NextResponse {
  res.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return res;
}

export async function POST() {
  return clear(NextResponse.json({ ok: true }));
}

export async function GET(req: Request) {
  const url = new URL("/login", req.url);
  return clear(NextResponse.redirect(url));
}
