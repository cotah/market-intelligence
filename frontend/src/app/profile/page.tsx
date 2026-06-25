"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FounderProfile } from "@/lib/types";

// Campos que sao listas (editados como texto separado por virgula).
const LIST_FIELDS: ReadonlyArray<keyof FounderProfile> = [
  "active_markets",
  "technical_skills",
  "business_skills",
  "target_business_type",
  "tools_available",
  "avoid",
  "languages",
];

const LABELS: Record<keyof FounderProfile, string> = {
  name: "Nome",
  current_country: "Pais atual",
  active_markets: "Mercados ativos",
  technical_skills: "Skills tecnicas",
  business_skills: "Skills de negocio",
  target_business_type: "Tipos de negocio preferidos",
  tools_available: "Ferramentas disponiveis",
  active_projects: "Projetos ativos",
  budget_range: "Faixa de orcamento",
  avoid: "Evitar",
  languages: "Idiomas",
};

const HINTS: Partial<Record<keyof FounderProfile, string>> = {
  active_markets: "Separe por virgula. Ex: Brasil, Portugal",
  technical_skills: "Separe por virgula.",
  business_skills: "Separe por virgula.",
  target_business_type: "Separe por virgula. Ex: SaaS, Micro-SaaS",
  tools_available: "Separe por virgula.",
  avoid: "Separe por virgula. O que voce nao quer construir.",
  languages: "Separe por virgula. Ex: Portugues, Ingles",
  budget_range: "Ex: bootstrap, ate 5k, ate 20k",
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<FounderProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getFounderProfile();
      setProfile(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar o perfil");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function setField(field: keyof FounderProfile, value: string) {
    if (!profile) return;
    if (LIST_FIELDS.includes(field)) {
      const list = value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      setProfile({ ...profile, [field]: list });
    } else {
      setProfile({ ...profile, [field]: value });
    }
  }

  async function save() {
    if (!profile) return;
    setBusy(true);
    setFlash(null);
    try {
      const saved = await api.saveFounderProfile(profile);
      setProfile(saved);
      setFlash("Perfil salvo. O proximo ciclo da pipeline ja usa essas informacoes.");
    } catch (e) {
      setFlash(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Perfil do fundador</h1>
          <p className="text-sm text-zinc-500">
            Usado pelo agente de compatibilidade para pontuar oportunidades de acordo com
            o seu pais, mercados e skills.
          </p>
        </div>
        {profile && (
          <button
            onClick={save}
            disabled={busy}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-40"
          >
            {busy ? "Salvando..." : "Salvar"}
          </button>
        )}
      </div>

      {flash && <p className="text-xs text-zinc-400">{flash}</p>}
      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      {loading ? (
        <p className="py-12 text-center text-sm text-zinc-500">Carregando...</p>
      ) : profile ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {(Object.keys(LABELS) as Array<keyof FounderProfile>).map((field) => (
            <Field
              key={field}
              label={LABELS[field]}
              hint={HINTS[field]}
              value={
                LIST_FIELDS.includes(field)
                  ? (profile[field] as string[]).join(", ")
                  : (profile[field] as string)
              }
              multiline={field === "active_projects"}
              onChange={(v) => setField(field, v)}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Field({
  label,
  hint,
  value,
  multiline,
  onChange,
}: {
  label: string;
  hint?: string;
  value: string;
  multiline?: boolean;
  onChange: (value: string) => void;
}) {
  const base =
    "w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-emerald-500";
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm font-medium text-zinc-300">{label}</span>
      {multiline ? (
        <textarea
          value={value}
          rows={3}
          onChange={(e) => onChange(e.target.value)}
          className={base}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={base}
        />
      )}
      {hint && <span className="text-xs text-zinc-600">{hint}</span>}
    </label>
  );
}
