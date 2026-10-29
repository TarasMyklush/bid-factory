"""Model clients and the tier-enforcing router. See docs/data-protection.md.

- Tier A: Anthropic Claude via API (non-resident), or the in-country endpoint.
- Tier B: the in-country endpoint only (any OpenAI-compatible server on sovereign infrastructure).
- Tier C: no model, ever.

Call logs record task, tier, provider, model and token counts. Prompt and completion content is never logged.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .util import now_iso

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
# Models that support the server-side refusal fallback beta.
_FALLBACK_PREFIXES = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class TierViolation(RuntimeError):
    """Raised when data of a tier would reach a model that tier does not allow."""


class ModelError(RuntimeError):
    pass


class BaseModel:
    provider = "base"
    allowed_tiers: frozenset[str] = frozenset()

    def __init__(self, model: str, log_path: str | Path | None = None):
        self.model = model
        self.log_path = Path(log_path) if log_path else None

    def check_tier(self, tier: str) -> None:
        if tier == "C":
            raise TierViolation("Tier C material is handled by humans only; no model may process it")
        if tier not in self.allowed_tiers:
            raise TierViolation(
                f"Tier {tier} material may not be sent to provider '{self.provider}'"
                f" (allowed: {', '.join(sorted(self.allowed_tiers))})"
            )

    def _log(self, task: str, tier: str, usage_in: int | None, usage_out: int | None) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": now_iso(), "task": task, "tier": tier, "provider": self.provider, "model": self.model,
                 "input_tokens": usage_in, "output_tokens": usage_out}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def json(self, *, task: str, system: str, user: str, schema: dict, tier: str, max_tokens: int = 4000) -> dict:
        raise NotImplementedError

    def text(self, *, task: str, system: str, user: str, tier: str, max_tokens: int = 6000) -> str:
        raise NotImplementedError


def _strip_fences(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json|markdown|md)?\s*\n(.*)\n```$", t, flags=re.S)
    return m.group(1) if m else t


class AnthropicModel(BaseModel):
    """Claude via the official SDK. Non-resident: Tier A only."""

    provider = "anthropic"
    allowed_tiers = frozenset({"A"})

    def __init__(self, client: Any = None, model: str | None = None, log_path: str | Path | None = None):
        super().__init__(model or os.environ.get("BF_MODEL", DEFAULT_ANTHROPIC_MODEL), log_path)
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise ModelError("the anthropic package is not installed: pip install -e '.[anthropic]'") from exc
            client = anthropic.Anthropic()
        self.client = client

    def _create(self, request: dict) -> Any:
        if self.model.startswith(_FALLBACK_PREFIXES):
            return self.client.beta.messages.create(betas=[_FALLBACK_BETA], fallbacks="default", **request)
        return self.client.messages.create(**request)

    def _call(self, task: str, tier: str, request: dict) -> str:
        self.check_tier(tier)
        resp = self._create(request)
        usage = getattr(resp, "usage", None)
        self._log(task, tier, getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None))
        stop = getattr(resp, "stop_reason", None)
        if stop in ("refusal", "max_tokens"):
            raise ModelError(f"{task}: model stopped with {stop}")
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), None)
        if text is None:
            raise ModelError(f"{task}: no text in response")
        return text

    def json(self, *, task: str, system: str, user: str, schema: dict, tier: str, max_tokens: int = 4000) -> dict:
        request = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        )
        raw = self._call(task, tier, request)
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise ModelError(f"{task}: response was not valid JSON") from exc

    def text(self, *, task: str, system: str, user: str, tier: str, max_tokens: int = 6000) -> str:
        request = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium"},
        )
        return _strip_fences(self._call(task, tier, request))


class TierBModel(BaseModel):
    """An in-country model behind an OpenAI-compatible chat completions endpoint.

    Configure with BF_TIER_B_URL (base URL, e.g. https://llm.example.sa/v1), BF_TIER_B_MODEL and BF_TIER_B_KEY.
    Allowed for Tier A and Tier B. Whether the host is genuinely in-country is the operator's responsibility:
    record it on the client's data handling sheet.
    """

    provider = "tier-b"
    allowed_tiers = frozenset({"A", "B"})

    def __init__(self, url: str | None = None, model: str | None = None, key: str | None = None,
                 log_path: str | Path | None = None, opener: Callable[..., Any] | None = None):
        url = url or os.environ.get("BF_TIER_B_URL")
        if not url:
            raise ModelError("BF_TIER_B_URL is not set; no in-country model is configured")
        super().__init__(model or os.environ.get("BF_TIER_B_MODEL", "default"), log_path)
        self.url = url.rstrip("/") + "/chat/completions"
        self.key = key if key is not None else os.environ.get("BF_TIER_B_KEY", "")
        self.opener = opener or urllib.request.urlopen

    def _post(self, task: str, tier: str, body: dict) -> str:
        self.check_tier(tier)
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with self.opener(req, timeout=600) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ValueError) as exc:
            raise ModelError(f"{task}: tier-b request failed: {exc}") from exc
        usage = payload.get("usage") or {}
        self._log(task, tier, usage.get("prompt_tokens"), usage.get("completion_tokens"))
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError(f"{task}: unexpected tier-b response shape") from exc

    def json(self, *, task: str, system: str, user: str, schema: dict, tier: str, max_tokens: int = 4000) -> dict:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": task, "schema": schema}},
        }
        raw = _strip_fences(self._post(task, tier, body))
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise ModelError(f"{task}: response was not valid JSON") from exc

    def text(self, *, task: str, system: str, user: str, tier: str, max_tokens: int = 6000) -> str:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        return _strip_fences(self._post(task, tier, body))


class FakeModel(BaseModel):
    """Test double. `responder(task, system, user, schema)` returns a dict for json() or a str for text()."""

    provider = "fake"
    allowed_tiers = frozenset({"A", "B"})

    def __init__(self, responder: Callable[[str, str, str, dict | None], Any], log_path: str | Path | None = None):
        super().__init__("fake", log_path)
        self.responder = responder
        self.calls: list[dict] = []

    def json(self, *, task: str, system: str, user: str, schema: dict, tier: str, max_tokens: int = 4000) -> dict:
        self.check_tier(tier)
        self.calls.append({"task": task, "user": user})
        self._log(task, tier, None, None)
        return self.responder(task, system, user, schema)

    def text(self, *, task: str, system: str, user: str, tier: str, max_tokens: int = 6000) -> str:
        self.check_tier(tier)
        self.calls.append({"task": task, "user": user})
        self._log(task, tier, None, None)
        return self.responder(task, system, user, None)


CHOICES = ("auto", "rules", "anthropic", "tier-b")


def select_model(choice: str, tier: str, log_path: str | Path | None = None) -> BaseModel | None:
    """Return a model allowed for this tier, or None to run on deterministic rules only.

    auto: Tier A uses Claude when ANTHROPIC_API_KEY is set, else the in-country endpoint if configured, else rules.
          Tier B uses the in-country endpoint if configured, else rules. Tier C raises.
    """
    if tier == "C":
        raise TierViolation("Tier C material is handled by humans only; the toolkit will not process it")
    if choice == "rules":
        return None
    if choice == "anthropic":
        if tier != "A":
            raise TierViolation(f"Tier {tier} material may not be sent to a non-resident model (anthropic)")
        return AnthropicModel(log_path=log_path)
    if choice == "tier-b":
        return TierBModel(log_path=log_path)
    if choice == "auto":
        if tier == "A" and os.environ.get("ANTHROPIC_API_KEY"):
            return AnthropicModel(log_path=log_path)
        if os.environ.get("BF_TIER_B_URL"):
            return TierBModel(log_path=log_path)
        return None
    raise ValueError(f"unknown model choice {choice!r}; expected one of {CHOICES}")
