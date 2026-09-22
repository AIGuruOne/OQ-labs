"""One switch for every model the labs talk to.

This module is Interface Contract #3 (see docs/contracts.md). Every
notebook and script that calls a language model goes through it, so a
lab can move between a local Ollama model, the hosted API, and the
fine-tuned adapter by changing ONE string — never its code.

Public interface (stable — Day 3/4 notebooks and the Day 5 capstone
scaffold build against this):

    from config.endpoints import get_endpoint, list_endpoints

    llm = get_endpoint("hosted")          # "local" | "hosted" | "tuned"
    llm = get_endpoint()                  # uses LLM_ENDPOINT from .env

    text = llm.chat("Summarise this ticket: ...")
    text = llm.chat(
        "Summarise this ticket: ...",
        system="You are an IT service desk assistant.",
        temperature=0.0,
        max_tokens=512,
    )
    text = llm.chat(messages=[                     # full-control form
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
    ])

    record = llm.chat_json("Extract fields from: ...")   # -> dict

    llm.name        # "hosted"
    llm.model       # e.g. "gpt-4o-mini"
    llm.base_url    # e.g. "https://api.openai.com/v1"

How it works: all three backends speak the same OpenAI-compatible
`POST {base_url}/chat/completions` protocol. Ollama exposes it at
http://localhost:11434/v1, the hosted API at its own URL, and the
tuned adapter is just an Ollama model with a different name. One
protocol, three configurations — that is the whole trick, and it is
the same trick OQ can use in production.

Configuration comes from the environment (a `.env` file at the repo
root is loaded automatically — copy setup/.env.example). Nothing is
hardcoded:

    Endpoint "local":   OLLAMA_BASE_URL (default http://localhost:11434)
                        OLLAMA_MODEL    (default llama3.2:3b)
    Endpoint "hosted":  HOSTED_BASE_URL (default https://api.openai.com/v1)
                        HOSTED_MODEL    (default gpt-4o-mini)
                        OPENAI_API_KEY  (required)
    Endpoint "tuned":   OLLAMA_BASE_URL (same server as "local")
                        TUNED_MODEL     (default oq-ticket-tuned)
    Default endpoint:   LLM_ENDPOINT    (default "hosted")

Deliberately built on `requests` and the raw REST protocol rather than
a vendor SDK: the audience calls REST APIs daily, the protocol is the
lesson, and vendor SDKs change under us (the openai client had a
breaking major release in Aug 2026; this module does not care).
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load KEY=value lines from the repo-root .env into os.environ.

    Values already present in the environment win — a real exported
    variable always beats the file. Kept dependency-free on purpose so
    this module works before `pip install -r requirements.txt`.
    """
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


@dataclass
class EndpointConfig:
    """Everything needed to reach one OpenAI-compatible endpoint."""

    name: str          # "local" | "hosted" | "tuned"
    base_url: str      # ends with /v1
    model: str         # model name the server knows
    api_key: str       # "" where the server needs none (Ollama)


def _build_configs() -> dict:
    """Read the three endpoint configurations from the environment."""
    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_v1 = ollama_base.rstrip("/") + "/v1"

    return {
        "local": EndpointConfig(
            name="local",
            base_url=ollama_v1,
            model=os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
            api_key="",
        ),
        "hosted": EndpointConfig(
            name="hosted",
            base_url=os.environ.get(
                "HOSTED_BASE_URL", "https://api.openai.com/v1"
            ).rstrip("/"),
            model=os.environ.get("HOSTED_MODEL", "gpt-4o-mini"),
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        ),
        "tuned": EndpointConfig(
            name="tuned",
            base_url=ollama_v1,
            model=os.environ.get("TUNED_MODEL", "oq-ticket-tuned"),
            api_key="",
        ),
    }


# ---------------------------------------------------------------------------
# The endpoint object notebooks use
# ---------------------------------------------------------------------------


class EndpointError(RuntimeError):
    """Raised when an endpoint cannot be reached or returns an error.

    The message always says which endpoint failed and what to check —
    these surface in a room full of people under time pressure.
    """


class Endpoint:
    """A callable language-model endpoint. Create via get_endpoint()."""

    def __init__(self, config: EndpointConfig):
        self._config = config
        self.last_reply_info = None     # set by chat(): usage, model, finish_reason

    # -- read-only info -----------------------------------------------------

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def __repr__(self) -> str:
        return (
            f"Endpoint(name={self.name!r}, model={self.model!r}, "
            f"base_url={self.base_url!r})"
        )

    # -- the two calls notebooks make ---------------------------------------

    def chat(
        self,
        prompt: str = None,
        *,
        messages: list = None,
        system: str = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: int = 120,
        json_mode: bool = False,
    ) -> str:
        """Send one chat request, return the model's reply as a string.

        Give EITHER `prompt` (plus optional `system`) OR a full
        `messages` list — not both.
        """
        if (prompt is None) == (messages is None):
            raise ValueError("Pass exactly one of `prompt` or `messages`.")
        if messages is None:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            # Supported by the hosted API and by Ollama's OpenAI-compatible
            # endpoint. Belt-and-braces: chat_json() also repairs replies.
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        url = f"{self._config.base_url}/chat/completions"
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=timeout
            )
        except requests.exceptions.ConnectionError as err:
            raise EndpointError(
                f"Endpoint '{self.name}' unreachable at {url}. "
                + (
                    "Is Ollama running? Start it with `ollama serve` "
                    "(or run the Ollama install cell in this notebook)."
                    if self.name in ("local", "tuned")
                    else "Check HOSTED_BASE_URL and your network."
                )
            ) from err

        if response.status_code == 401:
            raise EndpointError(
                f"Endpoint '{self.name}' rejected the API key (HTTP 401). "
                "Check OPENAI_API_KEY in your .env file."
            )
        if response.status_code == 404 and self.name in ("local", "tuned"):
            raise EndpointError(
                f"Model '{self.model}' not found on Ollama (HTTP 404). "
                f"Pull it first: `ollama pull {self.model}` — or for the "
                "tuned endpoint, register the adapter as shown in the "
                "Day 2 fine-tune notebook."
            )
        if response.status_code != 200:
            raise EndpointError(
                f"Endpoint '{self.name}' returned HTTP "
                f"{response.status_code}: {response.text[:500]}"
            )

        body = response.json()
        # Kept for callers that log what a call cost (the Day 5 capstone's
        # audit line): tokens, the model version that answered, and whether
        # the reply was cut off by max_tokens.
        self.last_reply_info = {
            "usage": body.get("usage"),
            "model": body.get("model"),
            "finish_reason": body["choices"][0].get("finish_reason"),
        }
        return body["choices"][0]["message"]["content"]

    def chat_json(
        self,
        prompt: str = None,
        *,
        messages: list = None,
        system: str = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: int = 120,
    ) -> dict:
        """Like chat(), but parse the reply as JSON and return a dict.

        Uses the server's JSON mode where available, and strips code
        fences before parsing because small local models add them
        anyway. Raises EndpointError if the reply still is not JSON —
        a lesson in itself, so the error includes the raw reply.
        """
        raw = self.chat(
            prompt,
            messages=messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            json_mode=True,
        )
        cleaned = raw.strip()
        # Strip a Markdown code fence if the model wrapped its JSON in one.
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
        if fence:
            cleaned = fence.group(1)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as err:
            raise EndpointError(
                f"Endpoint '{self.name}' did not return valid JSON.\n"
                f"Raw reply was:\n{raw[:1000]}"
            ) from err


# ---------------------------------------------------------------------------
# Module-level entry points
# ---------------------------------------------------------------------------


def get_endpoint(name: str = None) -> Endpoint:
    """Return the named endpoint: "local", "hosted" or "tuned".

    With no argument, uses the LLM_ENDPOINT environment variable
    (default "hosted"). This is the one line notebooks change to
    switch models.
    """
    configs = _build_configs()
    if name is None:
        name = os.environ.get("LLM_ENDPOINT", "hosted")
    if name not in configs:
        raise ValueError(
            f"Unknown endpoint {name!r}. Choose one of: "
            f"{', '.join(sorted(configs))}"
        )
    config = configs[name]
    if config.name == "hosted" and not config.api_key:
        raise EndpointError(
            "Endpoint 'hosted' needs OPENAI_API_KEY. Copy "
            "setup/.env.example to .env at the repo root and fill it in."
        )
    return Endpoint(config)


def list_endpoints() -> dict:
    """Return {name: description} for the three endpoints — no secrets."""
    configs = _build_configs()
    return {
        name: f"{cfg.model} @ {cfg.base_url}" for name, cfg in configs.items()
    }


if __name__ == "__main__":
    # Quick self-description when run directly. Makes no network calls.
    print("Configured endpoints (from environment / .env):")
    for name, desc in list_endpoints().items():
        print(f"  {name:<7} -> {desc}")
    print(f"\nDefault (LLM_ENDPOINT): {os.environ.get('LLM_ENDPOINT', 'hosted')}")
