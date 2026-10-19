from dataclasses import dataclass
import os
import httpx


class ProviderError(Exception):
    """Safe error message; never includes provider payloads or credentials."""


@dataclass(frozen=True)
class Reply:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class APIProvider:
    def __init__(self, name, model, key, client=None):
        if name not in {"GPT", "Claude"}:
            raise ValueError("Unknown provider")
        if not model.strip() or not key.strip():
            raise ValueError(f"Configure the {name} model and API key first")
        self.name, self.model, self._key = name, model.strip(), key.strip()
        self._client = client

    def complete(self, system, prompt, max_tokens):
        try:
            if self._client is not None:
                return self._request(self._client, system, prompt, max_tokens)
            with httpx.Client(timeout=90, follow_redirects=False) as client:
                return self._request(client, system, prompt, max_tokens)
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError(f"{self.name}: request failed or response was invalid") from None

    def _request(self, client, system, prompt, max_tokens):
        if self.name == "GPT":
            response = client.post("https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self._key}"},
                json={"model": self.model, "instructions": system, "input": prompt,
                      "max_output_tokens": max_tokens, "store": False})
        else:
            response = client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"},
                json={"model": self.model, "system": system,
                      "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens})
        if not response.is_success:
            raise ProviderError(f"{self.name}: HTTP {response.status_code}; check access, model and quota")
        data = response.json()
        usage = data.get("usage") or {}
        if self.name == "GPT":
            if data.get("status") != "completed":
                raise ProviderError("GPT: incomplete response; increase output limit or reduce context")
            text = "\n".join(part["text"] for item in data.get("output", [])
                if item.get("type") == "message" for part in item.get("content", [])
                if part.get("type") == "output_text")
        else:
            if data.get("stop_reason") != "end_turn":
                raise ProviderError("Claude: incomplete response; increase output limit or reduce context")
            text = "\n".join(item["text"] for item in data.get("content", []) if item.get("type") == "text")
        if not text.strip():
            raise ProviderError(f"{self.name}: empty or refused response")
        return Reply(text, usage.get("input_tokens"), usage.get("output_tokens"))


def live_providers():
    # Keys stay server-side and are never placed in the run record.
    return {name: APIProvider(name, os.getenv(f"{prefix}_MODEL", ""),
                              os.getenv(f"{prefix}_API_KEY", ""))
            for name, prefix in (("GPT", "OPENAI"), ("Claude", "ANTHROPIC"))}


class DemoProvider:
    """Scripted demonstration, not evidence of model quality."""
    model = "scripted-demo"

    def __init__(self, name):
        self.name = name

    def complete(self, system, prompt, max_tokens):
        if "REVIEW_JSON" in system:
            import json
            return Reply(json.dumps({"verdict": "needs_changes", "findings": [{
                "severity": "medium", "location": "provided context",
                "issue": "DEMO: verify the zero-input case against the acceptance criteria.",
                "suggestion": "Add a regression test and document the expected behavior."}]}))
        return Reply("DEMO ONLY — scripted proposal.\n\nAdd an explicit zero-input guard, "
                     "then add a regression test. No files were changed.\n\n"
                     "In live mode this panel contains the model's proposed code or patch.")
