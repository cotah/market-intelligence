// Sessao assinada (HMAC-SHA256 via Web Crypto). Funciona tanto no runtime
// Edge (middleware) quanto no Node (rotas). Nao guarda nada no servidor:
// o cookie carrega { sub, exp } + assinatura; se a assinatura nao bater ou
// expirar, a sessao e invalida.

const enc = new TextEncoder();

function b64url(bytes: Uint8Array): string {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlToBytes(s: string): Uint8Array {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function hmac(data: string, secret: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(data));
  return new Uint8Array(sig);
}

function timingSafeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export interface Session {
  sub: string;
  exp: number;
}

export const SESSION_COOKIE = "mi_session";
export const SESSION_TTL_SECONDS = 60 * 60 * 12; // 12h

export async function createSessionToken(
  sub: string,
  secret: string,
  ttlSeconds: number = SESSION_TTL_SECONDS,
): Promise<string> {
  const payload: Session = {
    sub,
    exp: Math.floor(Date.now() / 1000) + ttlSeconds,
  };
  const p = b64url(enc.encode(JSON.stringify(payload)));
  const sig = b64url(await hmac(p, secret));
  return `${p}.${sig}`;
}

export async function verifySessionToken(
  token: string | undefined,
  secret: string,
): Promise<Session | null> {
  if (!token || !secret) return null;
  const dot = token.indexOf(".");
  if (dot < 0) return null;
  const p = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const expected = await hmac(p, secret);
  if (!timingSafeEqual(b64urlToBytes(sig), expected)) return null;
  try {
    const payload = JSON.parse(
      new TextDecoder().decode(b64urlToBytes(p)),
    ) as Session;
    if (
      typeof payload.exp !== "number" ||
      payload.exp < Math.floor(Date.now() / 1000)
    ) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}
