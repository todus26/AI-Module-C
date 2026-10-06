import json

import pytest

from core.ai_recipe import AiGenerationError, AiUnavailableError, generate_recipes, parse_recipes


class FakeClient:
    def __init__(self, content=None, error=None):
        self.content, self.error = content, error
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        if self.error:
            raise self.error

        class Msg:
            content = self.content

        class Choice:
            message = Msg()

        class Resp:
            choices = [Choice()]

        return Resp()


VALID = json.dumps(
    {
        "recipes": [
            {
                "name": "양파볶음",
                "servings": 2,
                "time_min": 10,
                "difficulty": "쉬움",
                "calories": 120,
                "ingredients": [{"name": "양파", "amount": "1개"}],
                "seasonings": [{"name": "소금", "amount": "약간"}],
                "steps": ["썬다.", "볶는다."],
            }
        ]
    }
)


def test_valid_response_becomes_ai_recipes():
    recipes = generate_recipes(["양파"], client=FakeClient(VALID))
    assert recipes[0].name == "양파볶음" and recipes[0].source == "ai"


def test_malformed_response_raises_generation_error():
    with pytest.raises(AiGenerationError):
        parse_recipes("not json")
    with pytest.raises(AiGenerationError):
        parse_recipes(json.dumps({"recipes": [{"name": "x"}]}))


def test_api_failure_is_wrapped():
    with pytest.raises(AiGenerationError):
        generate_recipes(["양파"], client=FakeClient(error=RuntimeError("boom")))


def test_missing_key_raises_unavailable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AiUnavailableError):
        generate_recipes(["양파"])


def test_no_ingredients_is_rejected():
    with pytest.raises(AiGenerationError):
        generate_recipes([], client=FakeClient(VALID))
