from __future__ import annotations

import json
import re
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> str:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMError("Model response did not contain a JSON object.")
    return match.group(0)


class LLMClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080/v1/chat/completions",
        model: str = "local-qwen2.5-3b-instruct",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def complete_json(self, prompt: str, schema: type[T], temperature: float = 0.1) -> T:
        content = self._chat(prompt, temperature)
        try:
            return schema.model_validate_json(extract_json(content))
        except (ValidationError, ValueError, LLMError) as exc:
            repair_prompt = (
                "Repair this response so it is valid JSON for the requested schema. "
                "Return JSON only, with no markdown or commentary.\n\n"
                f"Original prompt:\n{prompt}\n\nInvalid response:\n{content}\n\nError:\n{exc}"
            )
            repaired = self._chat(repair_prompt, 0.0)
            try:
                return schema.model_validate_json(extract_json(repaired))
            except (ValidationError, ValueError, LLMError) as repair_exc:
                raise LLMError(f"Could not parse validated JSON after repair: {repair_exc}") from repair_exc

    def _chat(self, prompt: str, temperature: float) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You return strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            response = requests.post(self.base_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(f"Could not reach local LLM server at {self.base_url}: {exc}") from exc
        data = response.json()
        return data["choices"][0]["message"]["content"]


def to_json(data: object) -> str:
    if hasattr(data, "model_dump"):
        return data.model_dump_json(indent=2)
    return json.dumps(data, indent=2)
