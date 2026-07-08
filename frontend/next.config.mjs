import path from "path";
import { fileURLToPath } from "url";
import { withSentryConfig } from "@sentry/nextjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Evita o aviso de "multiple lockfiles": fixa a raiz neste projeto.
  outputFileTracingRoot: __dirname,
};

export default withSentryConfig(nextConfig, {
  org: "capivarex-real",
  project: "market-intelligence-frontend",
  // Sem SENTRY_AUTH_TOKEN o upload de sourcemap e pulado (build nao quebra).
  silent: !process.env.CI,
  disableLogger: true,
});
