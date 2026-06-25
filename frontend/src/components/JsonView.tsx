// Renderizador recursivo de JSON dos agentes.
// A saida dos LLMs varia, entao mostramos qualquer estrutura de forma legivel:
// objetos viram listas chave/valor, arrays viram listas, primitivos viram texto.

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function humanizeKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function JsonView({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-zinc-600">—</span>;
  }

  if (typeof value === "boolean") {
    return <span className="text-sky-400">{value ? "sim" : "nao"}</span>;
  }

  if (typeof value === "number" || typeof value === "string") {
    return <span className="text-zinc-200">{String(value)}</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-zinc-600">(vazio)</span>;
    return (
      <ul className="space-y-1.5">
        {value.map((item, i) => (
          <li
            key={i}
            className="rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-2"
          >
            <JsonView value={item} />
          </li>
        ))}
      </ul>
    );
  }

  if (isPlainObject(value)) {
    const entries = Object.entries(value);
    if (entries.length === 0) return <span className="text-zinc-600">(vazio)</span>;
    return (
      <dl className="space-y-2">
        {entries.map(([k, v]) => {
          const nested = isPlainObject(v) || Array.isArray(v);
          return (
            <div key={k} className={nested ? "" : "flex flex-wrap gap-x-2"}>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {humanizeKey(k)}
              </dt>
              <dd className={nested ? "mt-1" : "text-sm"}>
                <JsonView value={v} />
              </dd>
            </div>
          );
        })}
      </dl>
    );
  }

  return <span className="text-zinc-400">{String(value)}</span>;
}
