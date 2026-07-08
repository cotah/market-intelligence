"""Testes da logica de agendamento/continuidade do worker (risco #4)."""

from core import pipeline_control
from workers import pipeline_worker


def _fake_asyncio_run(summary):
    def run(coro):
        coro.close()  # evita 'coroutine never awaited'
        return summary
    return run


def test_scheduled_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(pipeline_control, "is_enabled", lambda: False)
    tried = {"lock": 0}
    monkeypatch.setattr(
        pipeline_control, "acquire_run_lock",
        lambda: tried.__setitem__("lock", tried["lock"] + 1) or True,
    )
    assert pipeline_worker.scheduled_run.apply().get() is None
    assert tried["lock"] == 0  # nem tentou pegar a trava


def test_scheduled_skips_when_already_running(monkeypatch):
    monkeypatch.setattr(pipeline_control, "is_enabled", lambda: True)
    monkeypatch.setattr(pipeline_control, "acquire_run_lock", lambda: False)
    ran = {"n": 0}
    monkeypatch.setattr(
        pipeline_worker.asyncio, "run",
        lambda c: (c.close(), ran.__setitem__("n", 1)),
    )
    assert pipeline_worker.scheduled_run.apply().get() is None
    assert ran["n"] == 0  # nao rodou a pipeline


def test_scheduled_runs_and_rechains(monkeypatch):
    monkeypatch.setattr(pipeline_control, "is_enabled", lambda: True)
    monkeypatch.setattr(pipeline_control, "acquire_run_lock", lambda: True)
    released = {"n": 0}
    monkeypatch.setattr(
        pipeline_control, "release_run_lock",
        lambda: released.__setitem__("n", released["n"] + 1),
    )
    monkeypatch.setattr(pipeline_control, "set_status", lambda d: None)
    summary = {"topics": 2, "kept": 1, "opportunity_ids": ["x"]}
    monkeypatch.setattr(pipeline_worker.asyncio, "run", _fake_asyncio_run(summary))
    rechained = {"n": 0}
    monkeypatch.setattr(
        pipeline_worker.scheduled_run, "apply_async",
        lambda **k: rechained.__setitem__("n", rechained["n"] + 1),
    )
    assert pipeline_worker.scheduled_run.apply().get() == summary
    assert released["n"] == 1   # liberou a trava
    assert rechained["n"] == 1  # re-encadeou a proxima rodada


def test_run_once_sets_status(monkeypatch):
    summary = {"topics": 3, "kept": 0, "opportunity_ids": []}
    monkeypatch.setattr(pipeline_worker.asyncio, "run", _fake_asyncio_run(summary))
    saved = {}
    monkeypatch.setattr(pipeline_control, "set_status", lambda d: saved.update(d))
    assert pipeline_worker.run_pipeline_once_task.apply().get() == summary
    assert saved["topics"] == 3  # gravou o status da rodada
