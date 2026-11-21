#!/usr/bin/env python3
"""
llm-utils.py
Object-Oriented Multi-Endpoint LLM Server Management Utility with YAML Configuration,
Strict Environment Overrides, and cURL Telemetry Mirroring.
"""

import argparse
import base64
import json
import logging
import os
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from argparse import RawTextHelpFormatter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure 'requests' library is installed and available
try:
    import requests
except ImportError:
    print(
        "Package 'requests' not found. Attempting automatic installation...",
        file=sys.stderr,
    )
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests

        print("Successfully installed 'requests'.", file=sys.stderr)
    except Exception as err:
        print(f"ERROR: Failed to install 'requests': {err}", file=sys.stderr)
        print(
            "Please install 'requests' manually via: pip install requests",
            file=sys.stderr,
        )
        sys.exit(1)

# Suppress noisy warnings
import urllib3
import yaml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

__scriptName__ = os.path.basename(sys.argv[0])
__version__ = "2026.11.03"
__updated__ = "03 November 2026"

log = logging.getLogger(__scriptName__)


def setup_logging(loglevel_str="INFO"):
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    log.setLevel(loglevel)
    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        log.addHandler(handler)
    else:
        log.handlers[0].setLevel(loglevel)


def _get_env_override(dot_path: str, default_value: Any) -> Any:
    parts = dot_path.split(".")
    candidates = [
        "_".join(parts).upper(),
        f"LLM_UTILS_{'_'.join(parts).upper()}",
    ]
    if len(parts) >= 4 and parts[0] == "endpoints":
        runtime = parts[1].upper()
        node_name = parts[2].upper()
        attr = parts[3].upper()
        candidates.insert(0, f"LLM_UTILS_{runtime}_{node_name}_{attr}")
        candidates.insert(0, f"{runtime}_{node_name}_{attr}")
        candidates.insert(0, f"{runtime}_{attr}")
        candidates.insert(0, f"LLM_UTILS_{runtime}_{attr}")
    elif len(parts) >= 2:
        last_key = parts[-1].upper()
        runtime = (
            parts[-2].upper()
            if not parts[-2].isdigit()
            else (parts[-3].upper() if len(parts) >= 3 else None)
        )
        if runtime and last_key in ["API_KEY", "URL", "API-KEY"]:
            candidates.insert(0, f"LLM_UTILS_{runtime}_{last_key}")
            candidates.insert(0, f"{runtime}_{last_key}")

    for candidate in candidates:
        if candidate in os.environ:
            val = os.environ[candidate]
            if isinstance(default_value, bool):
                return val.lower() in ("1", "true", "yes")
            elif isinstance(default_value, int):
                return int(val)
            elif isinstance(default_value, float):
                return float(val)
            return val
    return default_value


def _parse_endpoints(raw_data: Any) -> List[Dict[str, str]]:
    results = []
    if isinstance(raw_data, dict):
        for name, data in raw_data.items():
            if isinstance(data, dict):
                url = data.get("url", "")
                ep = {"name": name, "url": url}
                if "api_key" in data:
                    ep["api_key"] = data["api_key"]
                results.append(ep)
            elif isinstance(data, str) and data:
                results.append({"name": name, "url": data, "api_key": ""})
    elif isinstance(raw_data, list):
        for idx, item in enumerate(raw_data):
            if isinstance(item, dict):
                url = item.get("url", "")
                if url:
                    ep = {
                        "name": item.get("name", f"endpoint-{idx + 1}"),
                        "url": url,
                        "api_key": item.get("api_key", ""),
                    }
                    results.append(ep)
            elif isinstance(item, str) and item:
                results.append(
                    {"name": f"endpoint-{idx + 1}", "url": item, "api_key": ""}
                )
    return results


def resolve_config_path(config_filename: str = "llm-config.yml") -> Optional[Path]:
    if "LLM_CONFIG" in os.environ:
        explicit_path = Path(os.environ["LLM_CONFIG"]).resolve()
        if explicit_path.is_file():
            return explicit_path
        log.warning(f"Explicit LLM_CONFIG path not found: {explicit_path}")

    cwd_path = Path.cwd() / config_filename
    if cwd_path.is_file():
        return cwd_path

    home_dir = Path.home()
    home_candidates = [
        home_dir / config_filename,
        home_dir / ".config" / "llm-utils" / config_filename,
        home_dir / ".config" / config_filename,
    ]
    for h_path in home_candidates:
        if h_path.is_file():
            return h_path

    script_dir = Path(__file__).resolve().parent
    script_path = script_dir / config_filename
    if script_path.is_file():
        return script_path

    return None


def load_config(config_filename: str = "llm-config.yml") -> Dict[str, Any]:
    config_path = resolve_config_path(config_filename)
    raw_config: Dict[str, Any] = {}

    if config_path and config_path.is_file():
        try:
            log.info(f"Loading configuration from: {config_path}")
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}
        except Exception as e:
            print(
                f"ERROR: Failed to parse configuration file {config_path}: {e}",
                file=sys.stderr,
            )
            log.error("Failed to parse configuration file %s: %s", config_path, e)
    else:
        log.warning(
            "No configuration file found in CWD, Home, or Script directories. Using built-in defaults."
        )

    def _resolve_dict(sub_tree: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        resolved = {}
        for key, value in sub_tree.items():
            current_path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                resolved[key] = _resolve_dict(value, prefix=current_path)
            else:
                resolved[key] = _get_env_override(current_path, value)
        return resolved

    return _resolve_dict(raw_config)


class LLMConfig:
    def __init__(self, config_filename: str = "llm-config.yml"):
        cfg = load_config(config_filename)
        self.log_level = cfg.get("logging", {}).get("level", "INFO")
        endpoints = cfg.get("endpoints", {})
        self.ollama_endpoints = _parse_endpoints(endpoints.get("ollama", {}))
        self.vllm_endpoints = _parse_endpoints(endpoints.get("vllm", {}))
        self.llama_endpoints = _parse_endpoints(endpoints.get("llama", {}))
        self.llmfit_endpoints = _parse_endpoints(endpoints.get("llmfit", {}))

        opts = cfg.get("options", {})
        self.connect_timeout = int(opts.get("connect_timeout", 5))
        self.max_timeout = int(opts.get("max_timeout", 120))
        self.verify_tiers = [
            int(x.strip())
            for x in str(opts.get("verify_tiers", "30000,90000,140000")).split(",")
        ]


# =====================================================================
# Object-Oriented Runtime Architecture
# =====================================================================


class LLMRuntime(ABC):
    def __init__(self, name: str, url: str, api_key: str, timeout: int):
        self.name = name
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def get_auth_headers(self) -> Dict[str, str]:
        headers = {}
        if not self.api_key:
            return headers
        if self.runtime_type == "ollama":
            if ":" in self.api_key:
                encoded = base64.b64encode(self.api_key.encode("utf-8")).decode("utf-8")
                headers["Authorization"] = f"Basic {encoded}"
            else:
                headers["Authorization"] = f"Basic {self.api_key}"
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def execute_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict] = None,
        timeout: Optional[int] = None,
        quiet: bool = False,
    ) -> Tuple[int, Any]:
        to = timeout or self.timeout
        hdrs = headers if headers is not None else self.get_auth_headers()

        curl_cmd = f"curl -sS --connect-timeout 5 --max-time {to}"
        if hdrs:
            for k, v in hdrs.items():
                if k.lower() == "authorization":
                    parts = v.split(" ", 1)
                    redacted_v = (
                        f"{parts[0]} [REDACTED]" if len(parts) > 1 else "[REDACTED]"
                    )
                else:
                    redacted_v = v
                curl_cmd += f" -H '{k}: {redacted_v}'"

        if method.upper() != "GET":
            curl_cmd += f" -X {method.upper()}"

        curl_cmd += f" {url}"

        if json_data is not None:
            payload_str = json.dumps(json_data)
            if len(payload_str) > 200:
                payload_str = payload_str[:197] + "..."
            curl_cmd += f" -d '{payload_str}'"

        # if log.isEnabledFor(logging.DEBUG):
        if not quiet:
            print(f">>> Running: {curl_cmd}")

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=hdrs,
                json=json_data,
                timeout=to,
                verify=False,
            )
            try:
                return response.status_code, response.json()
            except Exception:
                return response.status_code, response.text
        except Exception as e:
            return 0, str(e)

    @property
    @abstractmethod
    def runtime_type(self) -> str:
        pass

    @abstractmethod
    def health_check(self, index: int):
        pass

    @abstractmethod
    def display_models(self, index: int, show_json: bool):
        pass

    @abstractmethod
    def ping(self, index: int, explicit_model: Optional[str]):
        pass

    @abstractmethod
    def verify(
        self, index: int, explicit_model: Optional[str], verify_tiers: List[int]
    ) -> int:
        pass

    def discover_generative_model(self) -> Optional[str]:
        return None


class OpenAICompatibleRuntime(LLMRuntime, ABC):
    """Base class for OpenAI-compatible inference runtimes (vLLM, llama.cpp)."""

    def _get_target_and_base_urls(self) -> Tuple[str, str]:
        base_url = self.url[:-3] if self.url.endswith("/v1") else self.url
        target_url = self.url if self.url.endswith("/v1") else f"{self.url}/v1"
        return base_url, target_url

    def health_check(self, index: int):
        base_url, _ = self._get_target_and_base_urls()
        health_url = f"{base_url}/health"

        print("==========================================")
        print(f" {index}. Health Check [{self.runtime_type.upper()}]: {self.url}")
        print("==========================================")

        status, data = self.execute_request(health_url)
        if 200 <= status < 300:
            print(f"Status: OK (HTTP {status})")
            if isinstance(data, dict):
                print(json.dumps(data, indent=2))
            elif data:
                print(data)
        else:
            print(f"Status: FAILED (HTTP {status}) - {data}")
        print()

    def display_models(self, index: int, show_json: bool):
        _, target_url = self._get_target_and_base_urls()
        models_url = f"{target_url}/models"

        print("==========================================")
        print(f" {index}. Endpoint [{self.runtime_type.upper()}]: {self.url}")
        print("==========================================")

        status, data = self.execute_request(models_url)
        if status != 200:
            print(f"   Error: HTTP {status} - {data}")
            return

        if show_json:
            print(json.dumps(data, indent=2))
        else:
            models = data.get("data", [])
            for m in models:
                print(f" - {m.get('id')}")

    def discover_generative_model(self) -> Optional[str]:
        _, target_url = self._get_target_and_base_urls()
        status, data = self.execute_request(f"{target_url}/models", quiet=True)
        if status != 200 or not isinstance(data, dict):
            return None
        models = data.get("data", [])
        model_ids = [m.get("id") for m in models if m.get("id")]
        generative = [
            m
            for m in model_ids
            if not any(x in m.lower() for x in ["embed", "rerank", "bge", "minilm"])
        ]
        return generative[0] if generative else (model_ids[0] if model_ids else None)

    def ping(self, index: int, explicit_model: Optional[str]):
        _, target_url = self._get_target_and_base_urls()
        model = explicit_model or self.discover_generative_model()
        if not model:
            print(f"Error: Could not determine an available model on {self.url}.")
            return

        print("==========================================")
        print(
            f" {index}. Chat Completion Ping [{self.runtime_type.upper()}]: {self.url}"
        )
        print(f" Target Model: {model}")
        print("==========================================")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 10,
        }
        status, data = self.execute_request(
            f"{target_url}/chat/completions",
            method="POST",
            headers={**self.get_auth_headers(), "Content-Type": "application/json"},
            json_data=payload,
        )
        if status == 200:
            print(json.dumps(data, indent=2) if isinstance(data, dict) else data)
        else:
            print(f"Error: HTTP {status} - {data}")
        print()

    def verify(
        self, index: int, explicit_model: Optional[str], verify_tiers: List[int]
    ) -> int:
        base_url, target_url = self._get_target_and_base_urls()
        failed = 0

        print("==========================================")
        print(f" {index}. VERIFY [{self.runtime_type.upper()}]: {self.url}")
        print("==========================================")

        # 1) /health check
        h_status, _ = self.execute_request(f"{base_url}/health")
        if 200 <= h_status < 300:
            print(f"  [ok]   /health → HTTP {h_status}")
        else:
            print(f"  [FAIL] /health → HTTP {h_status or 'unreachable'}")
            failed = 1

        # 2) /v1/models check & discovery
        model = explicit_model or self.discover_generative_model()
        if model:
            print(f"  Target Model: {model}")
            print(f"  [ok]   /v1/models → serving: {model}")
        else:
            print(f"  [FAIL] /v1/models → no models listed or unreachable")
            print()
            return 1

        # 3) tool-calls round-trip
        tool_payload = {
            "model": model,
            "max_tokens": 64,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant with access to tools. You MUST use the provided tool to answer questions requiring external data.",
                },
                {
                    "role": "user",
                    "content": "What is the weather in Paris? Use the tool to find out.",
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get the current weather for a city",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                    "description": "City name",
                                }
                            },
                            "required": ["city"],
                        },
                    },
                }
            ],
        }
        t_status, t_data = self.execute_request(
            f"{target_url}/chat/completions",
            method="POST",
            headers={**self.get_auth_headers(), "Content-Type": "application/json"},
            json_data=tool_payload,
            timeout=self.timeout,
        )

        tool_name = None
        if t_status == 200 and isinstance(t_data, dict):
            try:
                tool_name = t_data["choices"][0]["message"]["tool_calls"][0][
                    "function"
                ]["name"]
            except Exception:
                content = (
                    t_data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                if "<function=" in content:
                    match = re.search(r"<function=([^>]+)", content)
                    if match:
                        tool_name = match.group(1)

        if 200 <= t_status < 300 and tool_name:
            print(
                f"  [ok]   tool-calls → model invoked {tool_name} (auto-tool-choice + parser active)"
            )
        elif 200 <= t_status < 300:
            print(
                f"  [warn] tool-calls → HTTP 200 but no tool_calls returned (model declined; parser status uncertain)"
            )
        else:
            err_msg = (
                t_data.get("error", {}).get("message", str(t_data))
                if isinstance(t_data, dict)
                else str(t_data)
            )
            print(f"  [FAIL] tool-calls → HTTP {t_status}: {err_msg[:160]}")
            failed = 1

        # 4) long-context ladder
        for words in verify_tiers:
            prompt_content = "lorem " * words
            ctx_payload = {
                "model": model,
                "max_tokens": 16,
                "messages": [{"role": "user", "content": prompt_content}],
            }
            c_status, c_data = self.execute_request(
                f"{target_url}/chat/completions",
                method="POST",
                headers={**self.get_auth_headers(), "Content-Type": "application/json"},
                json_data=ctx_payload,
                timeout=600,
            )

            total_tokens = "?"
            err_msg = ""
            if isinstance(c_data, dict):
                total_tokens = c_data.get("usage", {}).get("total_tokens", "?")
                err_msg = c_data.get("error", {}).get("message", "")

            if 200 <= c_status < 300:
                print(
                    f"  [ok]   context: {words} words → HTTP 200 (total_tokens={total_tokens})"
                )
            elif any(
                k in err_msg.lower()
                for k in [
                    "maximum context length",
                    "context_length",
                    "too many tokens",
                    "exceed",
                ]
            ):
                print(
                    f"  [info] context: {words} words → HTTP {c_status} ceiling enforced: {err_msg[:140]}"
                )
            else:
                print(
                    f"  [FAIL] context: {words} words → HTTP {c_status}: {err_msg[:140]}"
                )
                failed = 1

        print()
        return failed


class VLLMRuntime(OpenAICompatibleRuntime):
    @property
    def runtime_type(self) -> str:
        return "vllm"


class LlamaCppRuntime(OpenAICompatibleRuntime):
    @property
    def runtime_type(self) -> str:
        return "llama.cpp"


class OllamaRuntime(LLMRuntime):
    @property
    def runtime_type(self) -> str:
        return "ollama"

    def health_check(self, index: int):
        health_url = f"{self.url}/api/version"

        print("==========================================")
        print(f" {index}. Health Check [OLLAMA]: {self.url}")
        print("==========================================")

        status, data = self.execute_request(health_url)
        if 200 <= status < 300:
            print(f"Status: OK (HTTP {status})")
            if isinstance(data, dict):
                print(json.dumps(data, indent=2))
            elif data:
                print(data)
        else:
            print(f"Status: FAILED (HTTP {status}) - {data}")
        print()

    def display_models(self, index: int, show_json: bool):
        models_url = f"{self.url}/api/tags"

        print("==========================================")
        print(f" {index}. Endpoint [OLLAMA]: {self.url}")
        print("==========================================")

        status, data = self.execute_request(models_url)
        if status != 200:
            print(f"   Error: HTTP {status} - {data}")
            return

        if show_json:
            print(json.dumps(data, indent=2))
        else:
            models = data.get("models", [])
            for m in models:
                print(f" - {m.get('name')}")

    def ps(self, index: int):
        print("==========================================")
        print(f" {index}. Endpoint [OLLAMA]: {self.url} (/api/ps)")
        print("==========================================")
        status, data = self.execute_request(f"{self.url}/api/ps")
        if status == 200 and isinstance(data, dict):
            models = data.get("models", [])
            if not models:
                print("No models currently running in VRAM.")
            else:
                for m in models:
                    print(f" - {m.get('name')} (Size: {m.get('size', 'N/A')})")
        else:
            print(f"Error: HTTP {status} - {data}")
        print()

    def discover_generative_model(self) -> Optional[str]:
        # Check /api/ps first, then /api/tags, filtering out non-generative models
        for endpoint_path in ["/api/ps", "/api/tags"]:
            status, data = self.execute_request(
                f"{self.url}{endpoint_path}", quiet=True
            )
            if status == 200 and isinstance(data, dict):
                models = data.get("models", [])
                for m in models:
                    name = m.get("name", "")
                    if name and not any(
                        x in name.lower() for x in ["embed", "rerank", "bge", "minilm"]
                    ):
                        return name
                # If all models were filtered or list is empty, take the first available if tags
                if models and endpoint_path == "/api/tags":
                    for m in models:
                        name = m.get("name", "")
                        if name:
                            return name
        return None

    def ping(self, index: int, explicit_model: Optional[str]):
        model = explicit_model or self.discover_generative_model()
        if not model:
            print(
                f"Error: Could not determine an available generative model on {self.url}."
            )
            return

        print("==========================================")
        print(f" {index}. Chat Completion Ping [OLLAMA]: {self.url}")
        print(f" Target Model: {model}")
        print("==========================================")

        payload = {"model": model, "prompt": "ping", "stream": False}
        status, data = self.execute_request(
            f"{self.url}/api/generate",
            method="POST",
            headers={**self.get_auth_headers(), "Content-Type": "application/json"},
            json_data=payload,
            timeout=120,
        )
        if status == 200:
            print(json.dumps(data, indent=2) if isinstance(data, dict) else data)
        else:
            print(f"Error: HTTP {status} - {data}")
        print()

    def verify(
        self, index: int, explicit_model: Optional[str], verify_tiers: List[int]
    ) -> int:
        print("==========================================")
        print(f" {index}. VERIFY [OLLAMA]: {self.url}")
        print("==========================================")
        print("  [skip] 'verify' targets OpenAI-compatible endpoints (vLLM/llama.cpp).")
        print("         Ollama: use 'health' / 'ping' / 'ps' instead.")
        print()
        return 0

    def pull(self, model_name: str):
        if not model_name:
            print("Error: You must specify a model name to pull.")
            sys.exit(1)
        print("==========================================")
        print(f" Pulling '{model_name}' to {self.url}")
        print("==========================================")
        payload = {"name": model_name, "stream": False}
        status, data = self.execute_request(
            f"{self.url}/api/pull",
            method="POST",
            headers={**self.get_auth_headers(), "Content-Type": "application/json"},
            json_data=payload,
            timeout=600,
        )
        print(f"Result: HTTP {status} - {data}\n")

    def remove(self, model_name: str):
        if not model_name:
            print("Error: You must specify a model name to remove.")
            sys.exit(1)
        print("==========================================")
        print(f" Target Endpoint [OLLAMA]: {self.url}")
        print("==========================================")
        payload = {"model": model_name}
        status, data = self.execute_request(
            f"{self.url}/api/delete",
            method="DELETE",
            headers={**self.get_auth_headers(), "Content-Type": "application/json"},
            json_data=payload,
        )
        print(f"Result: HTTP {status} - {data}\n")


# =====================================================================
# LLMFit Recommendation Handler
# =====================================================================


def handle_llmfit(
    llmfit_endpoints: List[Any], args: Any, show_json: bool, timeout: int
):
    for idx, ep_item in enumerate(llmfit_endpoints, 1):
        if isinstance(ep_item, dict):
            base_url = ep_item.get("url", "").rstrip("/")
            ep_name = ep_item.get("name", f"endpoint-{idx}")
        else:
            base_url = str(ep_item).rstrip("/")
            ep_name = f"endpoint-{idx}"

        if not base_url:
            continue

        query_params = []
        if args.use_case:
            query_params.append(f"use_case={args.use_case}")
        if args.fit_filter:
            query_params.append(f"fit_filter={args.fit_filter}")
        if args.runtime:
            query_params.append(f"runtime={args.runtime}")
        if args.provider:
            query_params.append(f"provider={args.provider}")
        if args.limit:
            query_params.append(f"limit={args.limit}")

        target_url = f"{base_url}/api/v1/models/top"
        if query_params:
            target_url += "?" + "&".join(query_params)

        print("\n==========================================")
        print(f" {idx}. LLMFIT Recommendations [{ep_name}]: {base_url}")
        if args.use_case:
            print(f" Use Case: {args.use_case}")
        if args.limit:
            print(f" Limit: Top {args.limit}")
        print("==========================================")

        # Temporary dummy helper runtime for calling LLMFit request with telemetry logging
        dummy_rt = VLLMRuntime("llmfit", base_url, "", timeout)
        status, data = dummy_rt.execute_request(target_url, timeout=timeout)
        if status != 200:
            print(f"Error querying llmfit: HTTP {status} - {data}")
            continue

        if show_json:
            print(json.dumps(data, indent=2))
        else:
            models = data.get("models", [])
            if not models:
                print("No models returned.")
                continue

            print(
                f"{'MODEL':<45} | {'PROVIDER':<12} | {'PARAMS':<8} | {'FIT':<7} | {'MODE':<8} "
                f"| {'RUNTIME':<10} | {'SCORE':<6} | {'TPS':<6} | {'MEM%':<6} | {'CONTEXT':<8}"
            )
            print("-" * 135)
            for m in models:
                name = m.get("model") or m.get("name") or "N/A"
                prov = m.get("provider", "N/A")
                params = m.get("parameter_count") or m.get("params") or "N/A"
                fit = m.get("fit_label") or m.get("fit_level") or m.get("fit") or "N/A"
                mode = (
                    m.get("run_mode_label")
                    or m.get("run_mode")
                    or m.get("mode")
                    or "N/A"
                )
                runtime_lbl = m.get("runtime_label") or m.get("runtime") or "N/A"
                score = str(m.get("score", "N/A"))
                tps = str(m.get("estimated_tps") or m.get("tps") or "N/A")
                mem = str(m.get("utilization_pct") or m.get("mem_pct") or "N/A")
                context = str(m.get("context_length") or m.get("context") or "N/A")
                print(
                    f"{name:<45} | {prov:<12} | {params:<8} | {fit:<7} | {mode:<8} | {runtime_lbl:<10} "
                    f"| {score:<6} | {tps:<6} | {mem:<6} | {context:<8}"
                )


# =====================================================================
# Main Application Handler & CLI Routing
# =====================================================================


def main():
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("-L", "--loglevel", default=None)
    pre_args, _ = pre_parser.parse_known_args()

    setup_logging(pre_args.loglevel or "INFO")
    config = LLMConfig()
    setup_logging(pre_args.loglevel or config.log_level)

    prog_usage = f"""
Examples of use:
  {__scriptName__} display
  {__scriptName__} health
  {__scriptName__} ps
  {__scriptName__} ping
  {__scriptName__} verify
  {__scriptName__} recommend --use-case coding
  {__scriptName__} -L DEBUG display
"""

    parser = argparse.ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description="Object-Oriented Multi-Endpoint LLM Server Management Utility (Runtime-Centric)",
        epilog=prog_usage,
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-L",
        "--loglevel",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default=config.log_level,
    )
    parser.add_argument(
        "-j", "--json", action="store_true", help="Output raw JSON responses"
    )
    parser.add_argument(
        "-e", "--endpoint", action="append", help="Specify custom endpoint URL(s)"
    )
    parser.add_argument("--use-case", help="Filter recommendation use case")
    parser.add_argument("--fit-filter", help="Filter by fit level")
    parser.add_argument("--runtime", help="Filter by inference runtime")
    parser.add_argument("--provider", help="Filter recommendations by model provider")
    parser.add_argument("--limit", help="Limit number of returned recommendations")
    parser.add_argument(
        "command",
        nargs="?",
        default="display",
        help="Command: health, check, display, ls, list, ps, running, ping, verify, validate, pull, remove, recommend, llmfit",
    )
    parser.add_argument(
        "model_name", nargs="?", help="Target model name for verify/ping/pull/remove"
    )

    args = parser.parse_args()
    setup_logging(args.loglevel)

    # Instantiate runtime objects based on configuration
    runtimes: List[LLMRuntime] = []
    for ep in config.vllm_endpoints:
        runtimes.append(
            VLLMRuntime(
                ep["name"], ep["url"], ep.get("api_key", ""), config.connect_timeout
            )
        )
    for ep in config.llama_endpoints:
        runtimes.append(
            LlamaCppRuntime(
                ep["name"], ep["url"], ep.get("api_key", ""), config.connect_timeout
            )
        )
    for ep in config.ollama_endpoints:
        runtimes.append(
            OllamaRuntime(
                ep["name"], ep["url"], ep.get("api_key", ""), config.connect_timeout
            )
        )

    cmd = args.command.lower()

    if cmd in ["health", "check"]:
        for idx, rt in enumerate(runtimes, 1):
            rt.health_check(idx)
    elif cmd in ["display", "ls", "list"]:
        for idx, rt in enumerate(runtimes, 1):
            rt.display_models(idx, args.json)
    elif cmd in ["ps", "running"]:
        ollama_runtimes = [rt for rt in runtimes if isinstance(rt, OllamaRuntime)]
        for idx, rt in enumerate(ollama_runtimes, 1):
            rt.ps(idx)
    elif cmd in ["ping"]:
        for idx, rt in enumerate(runtimes, 1):
            rt.ping(idx, args.model_name)
    elif cmd in ["verify", "validate"]:
        verify_exit = 0
        for idx, rt in enumerate(runtimes, 1):
            code = rt.verify(idx, args.model_name, config.verify_tiers)
            if code != 0:
                verify_exit = 1

        print("==========================================")
        if verify_exit == 0:
            print(" VERIFY RESULT: ALL CHECKS PASSED")
        else:
            print(" VERIFY RESULT: FAILURES DETECTED — see [FAIL] lines above")
            print("==========================================")
            sys.exit(1)
        print("==========================================")
    elif cmd in ["pull", "download"]:
        ollama_runtimes = [rt for rt in runtimes if isinstance(rt, OllamaRuntime)]
        for rt in ollama_runtimes:
            rt.pull(args.model_name)
    elif cmd in ["remove", "rm", "delete"]:
        ollama_runtimes = [rt for rt in runtimes if isinstance(rt, OllamaRuntime)]
        for rt in ollama_runtimes:
            rt.remove(args.model_name)
    elif cmd in ["recommend", "llmfit"]:
        urls = args.endpoint if args.endpoint else config.llmfit_endpoints
        handle_llmfit(urls, args, args.json, config.max_timeout)
    else:
        log.error(f"Command '{cmd}' not recognized.")
        print(
            f"Command '{cmd}' not recognized. Use 'display', 'health', 'ps', 'ping', 'verify', or 'recommend'."
        )


if __name__ == "__main__":
    main()
