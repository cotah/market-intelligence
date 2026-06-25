"""Testes do parsing de JSON do wrapper de LLM e do perfil do fundador."""

import pytest

from core.founder_profile import get_profile_as_text
from core.exceptions import LLMException
from core.llm import _extract_json


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


def test_founder_profile_text_has_key_info():
    text = get_profile_as_text()
    assert "Henrique" in text
    assert "Dublin" in text
    assert "FastAPI" in text
