"""Testes do parsing de JSON do wrapper de LLM e do perfil do fundador."""

import pytest

from core.founder_profile import get_profile_as_text
from core.exceptions import LLMException
from core.llm import _extract_json, _is_bad_request


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    text = "Sure!\n```json\n{\"topics\": [1, 2]}\n```\nHope it helps"
    assert _extract_json(text) == {"topics": [1, 2]}


def test_extract_json_with_surrounding_text():
    text = 'Here is the result: {"score": 9.2} - done.'
    assert _extract_json(text) == {"score": 9.2}


def test_extract_json_array():
    assert _extract_json("[1, 2, 3]") == [1, 2, 3]


def test_extract_json_invalid_raises():
    with pytest.raises(LLMException):
        _extract_json("no json here at all")


def test_extract_json_repairs_truncated_object():
    # Resposta cortada pelo max_tokens no meio do 2o competidor.
    truncated = '{"competitors": [{"name": "A", "pricing": "$10"}, {"name": "B"'
    data = _extract_json(truncated)
    assert isinstance(data, dict)
    # Salva pelo menos o 1o competidor, que veio completo.
    assert data["competitors"][0]["name"] == "A"
    assert len(data["competitors"]) >= 1


def test_extract_json_repairs_truncated_array():
    truncated = '[{"x": 1}, {"x": 2}, {"x": 3'
    data = _extract_json(truncated)
    assert isinstance(data, list)
    assert data[0]["x"] == 1
    assert len(data) >= 2


def test_is_bad_request_detects_status_code():
    class FakeApiError(Exception):
        status_code = 400

    assert _is_bad_request(FakeApiError("boom")) is True


def test_is_bad_request_detects_text():
    assert _is_bad_request(Exception("HTTP/1.1 400 Bad Request")) is True


def test_is_bad_request_false_for_other_errors():
    assert _is_bad_request(Exception("connection timeout")) is False

    class FakeApiError(Exception):
        status_code = 429

    assert _is_bad_request(FakeApiError("rate limit")) is False


def test_founder_profile_text_has_key_info():
    text = get_profile_as_text()
    assert "Henrique" in text
    assert "Dublin" in text
    assert "FastAPI" in text
