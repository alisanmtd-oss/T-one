from __future__ import annotations

import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import usage as usage_meter
from .ai_data_gateway import provider_policy, redact_text_for_model
from .credential_store import (
    environment_credential_ref,
    resolve_credential,
    save_credential,
)


MULTI_AI_CONFIG = Path("config") / "multi_ai.json"
AI_WORKER_ONBOARDING = Path("config") / "ai_worker_onboarding.md"
DEFAULT_ONBOARDING_CONTEXT_CHARS = 12000
ALLOWED_API_KEY_ENVS = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "ZHIPU_API_KEY",
    "SILICONFLOW_API_KEY",
    "LONGCAT_API_KEY",
    "AGNES_API_KEY",
    "KIRO_API_KEY",
    "FAST_EXTRACTOR_API_KEY",
    "DASHSCOPE_API_KEY",
    "OPENROUTER_API_KEY",
    "XAI_API_KEY",
    "MISTRAL_API_KEY",
    "GROQ_API_KEY",
    "CUSTOM_AI_API_KEY",
    "CUSTOM_ANTHROPIC_API_KEY",
}


@dataclass(slots=True)
class LLMConfig:
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    name: str = "legacy-env"
    enabled: bool = True
    tasks: list[str] = field(default_factory=list)
    priority: int = 100
    timeout_seconds: int = 60
    temperature: float = 0.2
    api_key_env: str | None = None
    credential_ref: str | None = None
    api_format: str = "openai"
    headers: dict[str, str] = field(default_factory=dict)
    requires_api_key: bool = False
    policy_id: str = "unknown"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        base_url = os.getenv("AI_DIRECTOR_LLM_BASE_URL")
        return cls(
            name="legacy-env",
            base_url=base_url,
            api_key=os.getenv("AI_DIRECTOR_LLM_API_KEY"),
            model=os.getenv("AI_DIRECTOR_LLM_MODEL"),
            tasks=["default", "strategy", "extraction", "video_breakdown", "listing", "pod_ops", "chat"],
            priority=999,
            policy_id=infer_provider_policy_id("legacy-env", base_url),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, root: Path | None = None) -> "LLMConfig":
        api_key_env = str(payload.get("api_key_env") or "").strip() or None
        credential_ref = str(payload.get("credential_ref") or "").strip().lower() or None
        api_key = resolve_credential(
            root or Path.cwd(),
            credential_ref=credential_ref or "",
            api_key_env=api_key_env or "",
        )
        tasks = payload.get("tasks", [])
        if isinstance(tasks, str):
            tasks = [tasks]
        name = str(payload.get("name") or payload.get("id") or "unnamed-ai")
        base_url = str(payload.get("base_url") or "").strip() or None
        return cls(
            name=name,
            base_url=base_url,
            api_key=api_key,
            model=str(payload.get("model") or "").strip() or None,
            enabled=bool(payload.get("enabled", False)),
            tasks=[str(task) for task in tasks if str(task).strip()],
            priority=int(payload.get("priority", 100) or 100),
            timeout_seconds=int(payload.get("timeout_seconds", 60) or 60),
            temperature=float(payload.get("temperature", 0.2) or 0.2),
            api_key_env=api_key_env,
            credential_ref=credential_ref,
            api_format=str(payload.get("api_format") or "openai").strip().lower(),
            headers={str(k): str(v) for k, v in dict(payload.get("headers") or {}).items()},
            requires_api_key=bool(
                payload.get("requires_api_key", bool(api_key_env or credential_ref))
            ),
            policy_id=str(payload.get("policy_id") or infer_provider_policy_id(name, base_url)).strip().lower(),
        )

    @property
    def ready(self) -> bool:
        if not self.enabled or not self.base_url or not self.model:
            return False
        if self.requires_api_key and not self.api_key:
            return False
        return True


def infer_provider_policy_id(name: str, base_url: str | None = None) -> str:
    haystack = f"{name} {base_url or ''}".lower()
    if any(value in haystack for value in ("127.0.0.1", "localhost", "ollama", "lm-studio", "lm_studio")):
        return "local"
    if "openai" in haystack:
        return "openai"
    if "deepseek" in haystack:
        return "deepseek"
    if "gemini" in haystack or "generativelanguage.googleapis.com" in haystack:
        return "gemini"
    return "unknown"


@dataclass(slots=True)
class MultiAIStatus:
    configured: int
    ready: int
    providers: list[dict[str, Any]]
    routes: dict[str, list[str]]
    onboarding: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "ready": self.ready,
            "providers": self.providers,
            "routes": self.routes,
            "onboarding": self.onboarding,
        }


class AIProviderChainError(RuntimeError):
    def __init__(self, code: str, message: str, attempts: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.user_message = message
        self.attempts = list(attempts or [])

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "error": self.user_message,
            "attempts": [
                {
                    key: value
                    for key, value in attempt.items()
                    if key in {"provider", "model", "code", "error", "status_code"}
                }
                for attempt in self.attempts
            ],
        }


def classify_provider_error(
    exc: Exception,
    *,
    provider: str,
    model: str,
) -> dict[str, Any]:
    status_code = 0
    if isinstance(exc, urllib.error.HTTPError):
        status_code = int(exc.code or 0)
        if status_code in {401, 403}:
            code, message = "authentication_failed", "API Key 无效、无权限，或账号未开通该模型。"
        elif status_code == 404:
            code, message = "endpoint_or_model_not_found", "接口地址或模型 ID 不存在。"
        elif status_code == 429:
            code, message = "rate_limited", "供应商限流或额度不足，请检查余额与配额。"
        elif status_code in {400, 409, 422}:
            code, message = "request_rejected", "供应商拒绝了请求，请核对模型 ID、协议和账号权限。"
        elif status_code >= 500:
            code, message = "provider_unavailable", "供应商服务暂时不可用。"
        else:
            code, message = "http_error", f"供应商返回 HTTP {status_code}。"
    elif isinstance(exc, (TimeoutError, socket.timeout)):
        code, message = "timeout", "连接模型超时，请检查网络、接口地址或供应商状态。"
    elif isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            code, message = "timeout", "连接模型超时，请检查网络、接口地址或供应商状态。"
        else:
            code, message = "connection_failed", "无法连接模型接口，请检查网络和 Base URL。"
    elif isinstance(exc, (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError)):
        code, message = "invalid_response", "模型接口返回格式不兼容或缺少正文。"
    else:
        code, message = "provider_error", "模型调用失败，请重新测试当前配置。"
    return {
        "provider": provider,
        "model": model,
        "status": "failed",
        "code": code,
        "error": message,
        **({"status_code": status_code} if status_code else {}),
    }


def public_ai_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, AIProviderChainError):
        return exc.to_public_dict()
    return {
        "code": "ai_call_failed",
        "error": "AI 调用失败，系统没有执行真实店铺动作。",
        "attempts": [],
    }


class LLMClient:
    """Multi-AI OpenAI-compatible router.

    Each provider is expected to expose `/chat/completions`.
    Kiro, local models, OpenAI-compatible gateways, and other hosted models can all share this layer.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        *,
        root: Path | None = None,
        task: str = "default",
        provider: str | None = None,
        request_timeout_seconds: int | None = None,
        max_attempts: int | None = None,
    ) -> None:
        self.root = root
        self.task = task
        self.provider = provider
        self.request_timeout_seconds = (
            max(1, int(request_timeout_seconds)) if request_timeout_seconds else None
        )
        self.max_attempts = max(1, int(max_attempts)) if max_attempts else None
        self._single_config = config
        self._configs, self._routes = load_ai_configs(root)
        if config:
            self._configs = [config]
            self._routes = {"default": [config.name], task: [config.name]}

    @property
    def enabled(self) -> bool:
        return bool(self.available_configs(self.task))

    def status(self) -> MultiAIStatus:
        providers = []
        for config in self._configs:
            providers.append(
                {
                    "name": config.name,
                    "enabled": config.enabled,
                    "ready": config.ready,
                    "model": config.model or "",
                    "base_url": config.base_url or "",
                    "api_format": config.api_format,
                    "api_key_env": config.api_key_env or "",
                    "credential_ref": config.credential_ref or "",
                    "requires_api_key": config.requires_api_key,
                    "policy_id": config.policy_id,
                    "tasks": config.tasks,
                    "priority": config.priority,
                }
            )
        return MultiAIStatus(
            configured=len(self._configs),
            ready=len([config for config in self._configs if config.ready]),
            providers=providers,
            routes=self._routes,
            onboarding=ai_worker_onboarding_status(self.root),
        )

    def available_configs(self, task: str | None = None) -> list[LLMConfig]:
        task_name = task or self.task
        configs = [config for config in self._configs if config.ready]
        if self.provider:
            configs = [config for config in configs if config.name == self.provider]
            return configs
        routed_names = self._routes.get(task_name) or self._routes.get("default") or []
        if routed_names:
            by_name = {config.name: config for config in configs}
            return [by_name[name] for name in routed_names if name in by_name]
        configs = [
            config
            for config in configs
            if not config.tasks or task_name in config.tasks or "default" in config.tasks
        ]
        return sorted(configs, key=lambda item: item.priority)

    def chat(self, system_prompt: str, user_prompt: str, *, task: str | None = None, context: dict[str, Any] | None = None) -> str:
        return str(
            self.chat_with_metadata(
                system_prompt,
                user_prompt,
                task=task,
                context=context,
            )["text"]
        )

    def chat_with_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        task: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        configs = self.available_configs(task)
        if self.max_attempts:
            configs = configs[: self.max_attempts]
        if not configs:
            raise AIProviderChainError(
                "provider_not_ready",
                "当前任务没有可用模型：请先补齐 API Key、Base URL 和模型 ID，再执行连接测试。",
            )

        errors: list[dict[str, Any]] = []
        for config in configs:
            started_at = datetime.now(timezone.utc)
            try:
                policy = provider_policy(config.policy_id)
                include_onboarding = bool(
                    (context or {}).get("include_onboarding", True)
                    and policy.allow_onboarding
                )
                trained_system_prompt = (
                    add_ai_worker_onboarding(system_prompt, self.root)
                    if include_onboarding
                    else system_prompt.strip()
                )
                guarded_system_prompt = add_context_isolation_guard(trained_system_prompt, task or self.task, context)
                safe_system_prompt = redact_text_for_model(
                    guarded_system_prompt,
                    max_data_level=policy.max_data_level,
                    task=task or self.task,
                ).text
                safe_user_prompt = redact_text_for_model(
                    user_prompt,
                    max_data_level=policy.max_data_level,
                    task=task or self.task,
                ).text
                text = self._chat_once(
                    config,
                    safe_system_prompt,
                    safe_user_prompt,
                    task=task or self.task,
                    record=True,
                )
                return {
                    "text": text,
                    "provider": config.name,
                    "model": config.model or "",
                    "latency_ms": elapsed_ms(started_at),
                    "attempts": errors,
                }
            except Exception as exc:  # noqa: BLE001 - try the next configured model.
                errors.append(
                    classify_provider_error(
                        exc,
                        provider=config.name,
                        model=config.model or "",
                    )
                )
        first = errors[0] if errors else {}
        raise AIProviderChainError(
            str(first.get("code") or "all_providers_failed"),
            str(first.get("error") or "所有已配置模型均调用失败。"),
            errors,
        )

    def test_connections(self, *, task: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        configs = self.available_configs(task)
        for config in configs:
            started_at = datetime.now(timezone.utc)
            try:
                reply = self._chat_once(
                    config,
                    add_context_isolation_guard(
                        "You are an API health-check responder. Return only: OK.",
                        task or self.task,
                        {"scope": "health_check", "store_id": "none", "product_id": "none"},
                    ),
                    "Return OK. Do not include business analysis.",
                    task="health_check",
                    record=False,
                )
                results.append(
                    {
                        "provider": config.name,
                        "model": config.model or "",
                        "status": "ok" if "ok" in reply.lower() else "unexpected_reply",
                        "reply_preview": reply[:120],
                        "latency_ms": elapsed_ms(started_at),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - connection diagnostics should capture each provider.
                results.append({
                    **classify_provider_error(
                        exc,
                        provider=config.name,
                        model=config.model or "",
                    ),
                    "latency_ms": elapsed_ms(started_at),
                })
        return results

    def _chat_once(self, config: LLMConfig, system_prompt: str, user_prompt: str, *, task: str = "default", record: bool = False) -> str:
        if config.api_format == "anthropic":
            return self._chat_anthropic(config, system_prompt, user_prompt, task=task, record=record)
        return self._chat_openai_compatible(config, system_prompt, user_prompt, task=task, record=record)

    def _meter(self, config: LLMConfig, task: str, prompt_text: str, reply: str, usage: dict[str, Any] | None, record: bool) -> None:
        if not record or self.root is None:
            return
        usage = usage or {}
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        if prompt_tokens is None:
            prompt_tokens = len(prompt_text) // 4
        if completion_tokens is None:
            completion_tokens = len(reply) // 4
        usage_meter.record_usage(self.root, config.name, config.model or "", int(prompt_tokens or 0), int(completion_tokens or 0), task)

    def _chat_openai_compatible(self, config: LLMConfig, system_prompt: str, user_prompt: str, *, task: str = "default", record: bool = False) -> str:
        endpoint = config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": config.temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            **config.headers,
            **({"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}),
        }
        request = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
        timeout_seconds = min(
            config.timeout_seconds,
            self.request_timeout_seconds or config.timeout_seconds,
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty model response")
        content = content.strip()
        self._meter(config, task, system_prompt + user_prompt, content, data.get("usage"), record)
        return content

    def _chat_anthropic(self, config: LLMConfig, system_prompt: str, user_prompt: str, *, task: str = "default", record: bool = False) -> str:
        endpoint = config.base_url.rstrip("/") + "/v1/messages"
        payload = {
            "model": config.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": int(os.getenv("AI_DIRECTOR_MAX_TOKENS", "4096")),
            "temperature": config.temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            **config.headers,
        }
        if config.api_key:
            headers["x-api-key"] = config.api_key
        request = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
        timeout_seconds = min(
            config.timeout_seconds,
            self.request_timeout_seconds or config.timeout_seconds,
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        chunks = data.get("content", [])
        if isinstance(chunks, list):
            reply = "".join(str(chunk.get("text", "")) for chunk in chunks if isinstance(chunk, dict)).strip()
        else:
            reply = str(chunks)
        if not reply.strip():
            raise ValueError("empty model response")
        self._meter(config, task, system_prompt + user_prompt, reply, data.get("usage"), record)
        return reply


def load_ai_configs(root: Path | None = None) -> tuple[list[LLMConfig], dict[str, list[str]]]:
    configs: list[LLMConfig] = []
    routes: dict[str, list[str]] = {}
    config_path = (root / MULTI_AI_CONFIG) if root else Path(MULTI_AI_CONFIG)
    if config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
        providers = payload.get("providers", [])
        if isinstance(providers, list):
            configs.extend(
                LLMConfig.from_dict(item, root=root or Path.cwd())
                for item in providers
                if isinstance(item, dict)
            )
        raw_routes = payload.get("routes", {})
        if isinstance(raw_routes, dict):
            for task, names in raw_routes.items():
                if isinstance(names, str):
                    routes[str(task)] = [names]
                elif isinstance(names, list):
                    routes[str(task)] = [str(name) for name in names]

    legacy = LLMConfig.from_env()
    if legacy.ready:
        configs.append(legacy)
        routes.setdefault("default", []).append(legacy.name)
    return configs, routes


def ai_worker_onboarding_status(root: Path | None = None) -> dict[str, Any]:
    path = (root / AI_WORKER_ONBOARDING) if root else Path(AI_WORKER_ONBOARDING)
    enabled = os.getenv("AI_DIRECTOR_ONBOARDING_ENABLED", "1") != "0"
    max_chars = int(os.getenv("AI_DIRECTOR_ONBOARDING_MAX_CHARS", str(DEFAULT_ONBOARDING_CONTEXT_CHARS)))
    exists = path.exists()
    char_count = len(path.read_text(encoding="utf-8")) if exists else 0
    return {
        "enabled": enabled and exists,
        "path": str(path),
        "char_count": char_count,
        "max_chars": max_chars,
    }


def load_ai_worker_onboarding(root: Path | None = None) -> str:
    status = ai_worker_onboarding_status(root)
    if not status["enabled"]:
        return ""
    path = Path(str(status["path"]))
    text = path.read_text(encoding="utf-8").strip()
    max_chars = int(status["max_chars"])
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n[Onboarding pack truncated by AI_DIRECTOR_ONBOARDING_MAX_CHARS.]"
    return text


def add_ai_worker_onboarding(system_prompt: str, root: Path | None = None) -> str:
    onboarding = load_ai_worker_onboarding(root)
    clean_system_prompt = system_prompt.strip()
    if not onboarding:
        return clean_system_prompt
    if "AI Worker Onboarding Pack" in clean_system_prompt:
        return clean_system_prompt
    return (
        f"{onboarding}\n\n"
        "## Current Task Instructions\n"
        f"{clean_system_prompt or 'Follow the Global Commerce OS operating rules above.'}"
    ).strip()


def add_context_isolation_guard(system_prompt: str, task: str, context: dict[str, Any] | None = None) -> str:
    context = dict(context or {})
    context.setdefault("session_id", uuid4().hex[:12])
    context.setdefault("task", task or "default")
    allowed_keys = [
        "session_id",
        "task",
        "scope",
        "store_id",
        "country",
        "platform",
        "product_id",
        "product_target_id",
        "brand_id",
        "user_role",
    ]
    safe_context = {key: str(context.get(key) or "") for key in allowed_keys if context.get(key) is not None}
    guard = f"""

## AI Director Context Isolation
- One API account may serve many stores, countries, products and tasks, but every request is isolated by the scope below.
- Use only the context included in this request. Do not rely on memory, previous chats, other stores, other brands, other products, or other users unless they are explicitly included here.
- Do not merge data between stores, countries, platforms, products or customers.
- If the request lacks data, say what is missing instead of borrowing assumptions from another conversation.
- The application stores long-term memory outside the model. Treat the model as stateless for operating decisions.
- Never reveal, request, or store API keys, passwords, legal entity data, phone numbers, emails or login credentials in analysis output.
- Scope: {json.dumps(safe_context, ensure_ascii=False, sort_keys=True)}
"""
    return f"{system_prompt.rstrip()}\n{guard}".strip()


def elapsed_ms(started_at: datetime) -> int:
    return int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)


def configure_api_key(root: Path, env_name: str, api_key: str) -> dict[str, Any]:
    env_name = env_name.strip().upper()
    api_key = api_key.strip()
    if env_name not in ALLOWED_API_KEY_ENVS:
        raise ValueError(f"Unsupported API key environment variable: {env_name}")
    if not api_key:
        raise ValueError("API key cannot be empty.")

    os.environ[env_name] = api_key
    credential = save_credential(root, environment_credential_ref(env_name), api_key)
    enabled = enable_providers_for_env(root, env_name)
    return {
        "env_name": env_name,
        "credential_ref": credential["credential_ref"],
        "enabled_providers": enabled,
        "persist_status": credential["persist_status"],
    }


def persist_user_environment_variable(env_name: str, value: str) -> str:
    if os.name != "nt":
        return "process_only"
    try:
        subprocess.run(
            ["setx", env_name, value],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except Exception:
        return "process_only"
    return "windows_user_env"


def enable_providers_for_env(root: Path, env_name: str) -> list[str]:
    config_path = root / MULTI_AI_CONFIG
    if not config_path.exists():
        return []
    payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    providers = payload.get("providers", [])
    enabled: list[str] = []
    if not isinstance(providers, list):
        return enabled
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        if str(provider.get("api_key_env") or "").strip().upper() != env_name:
            continue
        provider["enabled"] = True
        provider["credential_ref"] = environment_credential_ref(env_name)
        enabled.append(str(provider.get("name") or "unnamed-ai"))
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return enabled
