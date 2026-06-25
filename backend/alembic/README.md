# Migrations (Alembic)

Gerar uma migration automaticamente a partir dos modelos:

```bash
uv run alembic revision --autogenerate -m "descricao"
```

Aplicar as migrations no banco:

```bash
uv run alembic upgrade head
```

A pasta `versions/` guarda os arquivos de migration. A URL do banco vem de
`core.config.Settings` (lida do `.env`), nunca hardcodada.
