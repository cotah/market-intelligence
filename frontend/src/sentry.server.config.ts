// Sentry no servidor (Node). No-op se nao houver DSN.
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment:
    process.env.SENTRY_ENVIRONMENT ?? process.env.VERCEL_ENV ?? "development",
  tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? 0),
  sendDefaultPii: false,
});
