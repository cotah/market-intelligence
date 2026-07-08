"use client";

// Captura erros de renderizacao do React (App Router) e envia ao Sentry.
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="pt-BR">
      <body className="min-h-screen antialiased">
        <div className="mx-auto max-w-md px-4 py-16 text-center text-zinc-200">
          <h2 className="mb-2 text-lg font-semibold">Algo deu errado.</h2>
          <p className="text-sm text-zinc-400">
            O erro foi registrado. Tente recarregar a página.
          </p>
        </div>
      </body>
    </html>
  );
}
