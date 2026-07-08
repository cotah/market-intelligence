// Login de usuario unico. Verifica email + senha contra variaveis de ambiente
// (APP_LOGIN_EMAIL / APP_LOGIN_PASSWORD_HASH) e emite um cookie de sessao
// assinado. A senha e guardada como hash scrypt (nunca em texto). Roda no
// runtime Node porque usa crypto.scrypt.

import { scrypt as _scrypt, timingSafeEqual } from "crypto";
import { promisify } from "util";

import { NextRequest, NextResponse } from "next/server";

import {
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  createSessionToken,
} from "@/lib/session";

export const runtime = "nodejs";

const scrypt = promisify(_scrypt) as (
  pw: string | Buffer,
  salt: string | Buffer,
  keylen: number,
) => Promise<Buffer>;

// Formato do hash: scrypt$<saltHex>$<hashHex> (gere com scripts/hash-password.mjs)
async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const parts = stored.split("$");
  if (parts.length !== 3 || parts[0] !== "scrypt") return false;
  const salt = Buffer.from(parts[1], "hex");
  const expected = Buffer.from(parts[2], "hex");
  if (expected.length === 0) return false;
  const got = await scrypt(password, salt, expected.length);
  return got.length === expected.length && timingSafeEqual(got, expected);
}

export async function POST(req: NextRequest) {
  const secret = process.env.SESSION_SECRET;
  const email = process.env.APP_LOGIN_EMAIL;
  const hash = process.env.APP_LOGIN_PASSWORD_HASH;
  if (!secret || !email || !hash) {
    return NextResponse.json(
      { detail: "Login nao configurado no servidor" },
      { status: 503 },
    );
  }

  let body: { email?: string; password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "JSON invalido" }, { status: 400 });
  }

  const okEmail =
    (body.email ?? "").trim().toLowerCase() === email.trim().toLowerCase();
  // Sempre roda a verificacao de senha para nao vazar (por tempo) se o email existe.
  const okPass = body.password ? await verifyPassword(body.password, hash) : false;

  if (!okEmail || !okPass) {
    return NextResponse.json(
      { detail: "Email ou senha invalidos" },
      { status: 401 },
    );
  }

  const token = await createSessionToken(email, secret);
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
  return res;
}
