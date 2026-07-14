"""Testes da logica de agendamento/continuidade do worker (risco #4).

Multi-tenancy: as tasks recebem o account_id da conta dona da rodada.
`scheduled_run` SEM account_id (Beat) vira dispatcher: enfileira uma
rodada por conta habilitada.
"""

from core import pipeline_control
from workers import pipeline_worker

ACC = "00000000-0000-0000-0000-000000000001"


def _fake_asyncio_run(summary):
    def run(coro):
        coro.close()  # evita 'coroutine never awaited'
        return summary
    return run


def test_scheduled_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(pipeline_control, "is_enabled", lambda account_id: False)
    tried = {"lock": 0}
    monkeypatch.setattr(
        pipeline_control, "acquire_run_lock",
        lambda account_id: tried.__setitem__("lock", tried["lock"] + 1) or True,
    )
    assert pipeline_worker.scheduled_run.apply(kwargs={"account_id": ACC}).get() is None
    assert tried["lock"] == 0  # nem tentou pegar a trava


def test_scheduled_skips_when_already_running(monkeypatch):
    monkeypatch.setattr(pipeline_control, "is_enabled", lambda account_id: True)
    monkeypatch.setattr(pipeline_control, "acquire_run_lock", lambda account_id: False)
    ran = {"n": 0}
    monkeypatch.setattr(
        pipeline_worker.asyncio, "run",
        lambda c: (c.close(), ran.__setitem__("n", 1)),
    )
    assert pipeline_worker.scheduled_run.apply(kwargs={"account_id": ACC}).get() is None
    assert ran["n"] == 0  # nao rodou a pipeline


def test_scheduled_runs_and_rechains(monkeypatch):
    monkeypatch.setattr(pipeline_control, "is_enabled", lambda account_id: True)
    monkeypatch.setattr(pipeline_control, "acquire_run_lock", lambda account_id: True)
    released = {"n": 0}
    monkeypatch.setattr(
        pipeline_control, "release_run_lock",
        lambda account_id: released.__setitem__("n", released["n"] + 1),
    )
    monkeypatch.setattr(pipeline_control, "set_status", lambda account_id, d: None)
    summary = {"topics": 2, "kept": 1, "opportunity_ids": ["x"]}
    monkeypatch.setattr(pipeline_worker.asyncio, "run", _fake_asyncio_run(summary))
    rechained = {"kwargs": None}
    monkeypatch.setattr(
        pipeline_worker.scheduled_run, "apply_async",
        lambda **k: rechained.__setitem__("kwargs", k),
    )
    assert pipeline_worker.scheduled_run.apply(kwargs={"account_id": ACC}).get() == summary
    assert released["n"] == 1  # liberou a trava
    # Re-encadeou a proxima rodada DA MESMA conta.
    assert rechained["kwargs"]["kwargs"] == {"account_id": ACC}


def test_scheduled_without_account_dispatches_per_enabled_account(monkeypatch):
    """Beat (sem account_id): enfileira uma rodada filha por conta habilitada."""
    monkeypatch.setattr(pipeline_control, "enabled_accounts", lambda: ["acc-a", "acc-b"])
    dispatched: list[str] = []
    monkeypatch.setattr(
        pipeline_worker.scheduled_run, "delay",
        lambda account_id: dispatched.append(account_id),
    )
    result = pipeline_worker.scheduled_run.apply().get()
    assert result == {"dispatched_accounts": 2}
    assert dispatched == ["acc-a", "acc-b"]


def test_run_once_sets_status(monkeypatch):
    summary = {"topics": 3, "kept": 0, "opportunity_ids": []}
    monkeypatch.setattr(pipeline_worker.asyncio, "run", _fake_asyncio_run(summary))
    saved = {}
    monkeypatch.setattr(
        pipeline_control, "set_status", lambda account_id, d: saved.update(d)
    )
    assert pipeline_worker.run_pipeline_once_task.apply(args=(ACC,)).get() == summary
    assert saved["topics"] == 3  # gravou o status da rodada
