#!/usr/bin/env bash

# Option Flags
SHOW_RAW_JSON=false
ACTION=""
ACTION_SET=false
MODEL_NAME=""
USE_CASE=""
FIT_FILTER=""
RUNTIME=""
PROVIDER=""
LIMIT=""
declare -a USER_LLM_ENDPOINTS=()
declare -a USER_LLMFIT_ENDPOINTS=()

# Define Default LLM Endpoints using Bash Associative Array
declare -A DEFAULT_LLM_ENDPOINTS=(
    ["https://vllm-coder.llm-rtx.johnson.int/v1"]="vllm"
    ["https://vllm-coder.llm-gb10.johnson.int/v1"]="vllm"
    ["https://vllm-exec.llm-gb10.johnson.int/v1"]="vllm"
    ["https://ollama.admin.johnson.int"]="ollama"
    #  ["${LLAMA_API_URL:-https://llama.llm-rtx.johnson.int/v1}"]="llama"
    #  ["https://llama.llm-gb10.johnson.int"]="llama"
)

# Define Default LLMFIT Endpoints using Bash Associative Array
declare -A DEFAULT_LLMFIT_ENDPOINTS=(
    ["${LLMFIT_API_URL:-https://llmfit.llm-gb10.johnson.int}"]="llmfit"
    ["${LLMFIT_RTX_API_URL:-https://llmfit.llm-rtx.johnson.int}"]="llmfit"
    ["${LLMFIT_ADMIN_API_URL:-https://llmfit.admin.johnson.int}"]="llmfit"
)

# 1. Increased timeout: Raised --max-time from 15s to 120s to allow model cold-loading
CURL_OPTS=(--connect-timeout 5 --max-time 120)

# verify: word counts for the long-context ladder (~1 word/token; the API's
# reported usage.total_tokens is the authoritative measurement)
VERIFY_TIERS="${VERIFY_TIERS:-30000,90000,140000}"
VERIFY_EXIT=0

# Helper execution function using array-based arguments
function exec_curl() {
    local endpoint_type="$1"
    shift
    local curl_args=("$@")

    # Format command string for logging with quotes around arguments containing spaces
    local log_cmd="curl -sS"
    local skip_next_mask=false

    for ((i = 0; i < ${#curl_args[@]}; i++)); do
        local arg="${curl_args[i]}"

        if [[ "${skip_next_mask}" == "true" ]]; then
            log_cmd+=" '[REDACTED]'"
            skip_next_mask=false
        elif [[ "${arg}" == "-u" ]]; then
            log_cmd+=" -u"
            skip_next_mask=true
        elif [[ "${arg}" =~ [[:space:]] ]]; then
            log_cmd+=" '${arg}'"
        else
            log_cmd+=" ${arg}"
        fi
    done

    # Apply standard header redactions to printable log output
    local masked_cmd
    masked_cmd=$(echo "${log_cmd}" | sed -E \
        -e 's/Authorization: Bearer [^ '\''"]+/Authorization: Bearer [REDACTED]/g' \
        -e 's/Authorization: Basic [^ '\''"]+/Authorization: Basic [REDACTED]/g' \
        -e 's/-u '\''[^'\'']+'\''/-u '\''[REDACTED]'\''/g')

    echo ">>> Running: ${masked_cmd}"

    # Capture HTTP Status Code along with response body
    local tmp_file
    tmp_file=$(mktemp)

    local http_code
    http_code=$(curl -sS "${curl_args[@]}" -w '%{http_code}' -o "${tmp_file}" 2>&1)
    local RETURN_STATUS=$?
    local output
    output=$(cat "${tmp_file}")
    rm -f "${tmp_file}"

    if [[ $RETURN_STATUS -ne 0 ]]; then
        echo "ERROR (exit status ${RETURN_STATUS}):"
        echo "${http_code}"
    else
        # Status validation for health and ping responses
        if [[ "${endpoint_type}" == "raw" || "${endpoint_type}" == "health" || "${endpoint_type}" == "ping" ]]; then
            if [[ "${http_code}" -ge 200 && "${http_code}" -lt 300 ]]; then
                echo "Status: OK (HTTP ${http_code})"
            else
                echo "Status: FAILED (HTTP ${http_code})"
            fi
        fi

        if [[ -n "${output}" ]]; then
            if echo "${output}" | jq . >/dev/null 2>&1; then
                if [[ "${SHOW_RAW_JSON}" == "true" || "${endpoint_type}" == "ping" ]]; then
                    echo "${output}" | jq
                else
                    # Extract model names by endpoint type
                    case "${endpoint_type}" in
                        ollama)
                            echo "${output}" | jq -r '.models[]?.name // empty' | sed 's/^/ - /'
                            ;;
                        vllm | llama)
                            echo "${output}" | jq -r '.data[]?.id // empty' | sed 's/^/ - /'
                            ;;
                        llmfit)
                            if echo "${output}" | jq -e '.models' >/dev/null 2>&1; then
                                printf "%-45s | %-12s | %-8s | %-7s | %-8s | %-10s | %-6s | %-6s | %-6s | %-8s\n" \
                                    "MODEL" "PROVIDER" "PARAMS" "FIT" "MODE" "RUNTIME" "SCORE" "TPS" "MEM%" "CONTEXT"
                                printf "%s\n" "------------------------------------------------------------------------------------------------------------------------"
                                # shellcheck disable=SC2162
                                echo "${output}" | jq -r '.models[]? | [
                                    (.model // .name // "N/A"),
                                    (.provider // "N/A"),
                                    (.parameter_count // .params // "N/A"),
                                    (.fit_label // .fit_level // .fit // "N/A"),
                                    (.run_mode_label // .run_mode // .mode // "N/A"),
                                    (.runtime_label // .runtime // "N/A"),
                                    (.score // "N/A"),
                                    (.estimated_tps // .tps // "N/A"),
                                    (.utilization_pct // .mem_pct // .mem_percent // "N/A"),
                                    (.context_length // .context // .max_context // "N/A")
                                ] | @tsv' | \
                                    while IFS=$'\t' read -s m p pa f mo r sc t mp c; do
                                        printf "%-45s | %-12s | %-8s | %-7s | %-8s | %-10s | %-6s | %-6s | %-6s | %-8s\n" \
                                            "$m" "$p" "$pa" "$f" "$mo" "$r" "$sc" "$t" "$mp" "$c"
                                    done
                            else
                                echo "${output}" | jq
                            fi
                            ;;
                        *)
                            echo "${output}" | jq
                            ;;
                    esac
                fi
            else
                echo "${output}"
            fi
        fi
    fi
    echo ""
}

# Helper to populate auth flags array for Bearer Token Auth Headers (vLLM and Llama)
function get_bearer_auth_args() {
    local endpoint_type="$1"
    local key=""

    if [[ "${endpoint_type}" == "llama" ]]; then
        key="${LLAMA_API_KEY:-${VLLM_API_KEY}}"
    elif [[ "${endpoint_type}" == "vllm" ]]; then
        key="${VLLM_API_KEY}"
    fi

    if [[ -n "${key}" ]]; then
        echo "-H"
        echo "Authorization: Bearer ${key}"
    fi
}

# Helper to populate auth flags array for Ollama Basic Auth Header / Option
function get_ollama_auth_args() {
    if [[ -n "${OLLAMA_API_KEY}" ]]; then
        # If the key contains a colon, it's raw 'user:password'
        if [[ "${OLLAMA_API_KEY}" == *":"* ]]; then
            echo "-u"
            echo "${OLLAMA_API_KEY}"
        else
            echo "-H"
            echo "Authorization: Basic ${OLLAMA_API_KEY}"
        fi
    fi
}

# Helper to sort models by estimated parameter count (lightest first)
function sort_by_lightest() {
    awk '{
    model = $0;
    size = 999999;
    if (match(model, /:([0-9\.]+)b/)) {
      size = substr(model, RSTART+1, RLENGTH-2) + 0;
    } else if (match(model, /-([0-9\.]+)b/)) {
      size = substr(model, RSTART+1, RLENGTH-2) + 0;
    }
    print size, model;
  }' | sort -n | awk '{print $2}'
}

# 2 & 3. Enhanced discovery:
# - Prefers active models loaded in VRAM (/api/ps)
# - Filters out non-generative models (embed/rerank)
# - Prefers lighter-weight models sorted by parameter count
function discover_model() {
    local type="$1"
    local url="$2"
    local discovered_model=""

    if [[ "${type}" == "vllm" || "${type}" == "llama" ]]; then
        local target_url="${url}"
        [[ "${target_url}" != *"/v1"* ]] && target_url="${target_url}/v1"
        readarray -t auth_args < <(get_bearer_auth_args "${type}")

        # Query vLLM /models list, filter non-generative models, and sort by parameter weight
        discovered_model=$(curl -sS "${CURL_OPTS[@]}" "${auth_args[@]}" "${target_url}/models" 2>/dev/null |
            jq -r '.data[]?.id // empty' 2>/dev/null |
            grep -vE 'embed|rerank|bge|minilm' |
            sort_by_lightest |
            head -n1)

    elif [[ "${type}" == "ollama" ]]; then
        readarray -t auth_args < <(get_ollama_auth_args)

        # First Check: Pre-loaded models currently resident in VRAM via /api/ps
        discovered_model=$(curl -sS "${CURL_OPTS[@]}" "${auth_args[@]}" "${url}/api/ps" 2>/dev/null |
            jq -r '.models[]?.name // empty' 2>/dev/null |
            grep -vE 'embed|rerank|bge|minilm' |
            sort_by_lightest |
            head -n1)

        # Second Check: If no generative model is in VRAM, query /api/tags and pick the lightest available model
        if [[ -z "${discovered_model}" ]]; then
            discovered_model=$(curl -sS "${CURL_OPTS[@]}" "${auth_args[@]}" "${url}/api/tags" 2>/dev/null |
                jq -r '.models[]?.name // empty' 2>/dev/null |
                grep -vE 'embed|rerank|bge|minilm' |
                sort_by_lightest |
                head -n1)
        fi
    fi

    echo "${discovered_model}"
}

# Long-context tier probe: synthetic N-word prompt, report status + total_tokens
function verify_long_context_tier() {
    local type="$1" url="$2" model="$3" words="$4"
    local target_url="${url}"
    [[ "${target_url}" != *"/v1"* ]] && target_url="${target_url}/v1"
    local auth_args=()
    readarray -t auth_args < <(get_bearer_auth_args "${type}")

    local out_file payload_file prompt_file
    out_file=$(mktemp)
    payload_file=$(mktemp)
    prompt_file=$(mktemp)

    # 1. Generate the huge prompt text directly into a temporary file
    awk -v n="${words}" 'BEGIN{for(i=0;i<n;i++) printf "lorem "}' > "${prompt_file}"

    # 2. Use jq --rawfile to read the file safely into $content as a raw string
    jq -n \
        --arg model "${model}" \
        --argjson max_tokens 16 \
        --rawfile content "${prompt_file}" \
        '{model: $model, max_tokens: $max_tokens, messages: [{role: "user", content: $content}]}' \
        > "${payload_file}"

    rm -f "${prompt_file}"

    local code
    code=$(curl -sS -o "${out_file}" -w '%{http_code}' --connect-timeout 5 --max-time 600 \
        "${auth_args[@]}" -H "Content-Type: application/json" \
        -X POST "${target_url}/chat/completions" \
        -d "@${payload_file}" \
        2>/dev/null)

    local total_tokens err_msg
    total_tokens=$(jq -r '.usage.total_tokens // empty' "${out_file}" 2>/dev/null)
    err_msg=$(jq -r '.error.message // empty' "${out_file}" 2>/dev/null)
    rm -f "${out_file}" "${payload_file}"

    if [[ "${code}" =~ ^2 ]]; then
        echo "  [ok]   context: ${words} words → HTTP 200 (total_tokens=${total_tokens:-?})"
    elif echo "${err_msg}" | grep -qi "maximum context length\|context_length\|too many tokens\|exceed"; then
        echo "  [info] context: ${words} words → HTTP ${code} ceiling enforced: ${err_msg:0:140}"
    elif [[ -z "${code}" || "${code}" == "000" ]]; then
        echo "  [FAIL] context: ${words} words → connection failure/timeout"
        return 1
    else
        echo "  [FAIL] context: ${words} words → HTTP ${code}: ${err_msg:0:140}"
        return 1
    fi
    return 0
}

# Full verification pass for one OpenAI-compatible (vLLM/Llama) endpoint
function verify_openai_endpoint() {
    local type="$1" url="$2" model="$3"
    local failed=0
    local target_url="${url}"
    [[ "${target_url}" != *"/v1"* ]] && target_url="${target_url}/v1"
    local base_url="${url%/v1}"
    local auth_args=()
    readarray -t auth_args < <(get_bearer_auth_args "${type}")

    # --- 1) /health --------------------------------------------------------------
    local code
    code=$(curl -sS -o /dev/null -w '%{http_code}' "${CURL_OPTS[@]}" "${auth_args[@]}" "${base_url}/health" 2>/dev/null)
    if [[ "${code}" =~ ^2 ]]; then
        echo "  [ok]   /health → HTTP ${code}"
    else
        echo "  [FAIL] /health → HTTP ${code:-unreachable}"
        failed=1
    fi

    # --- 2) /v1/models -----------------------------------------------------------
    local models_json served
    models_json=$(curl -sS "${CURL_OPTS[@]}" "${auth_args[@]}" "${target_url}/models" 2>/dev/null)
    served=$(echo "${models_json}" | jq -r '.data[]?.id // empty' 2>/dev/null | head -n1)
    if [[ -n "${served}" ]]; then
        echo "  [ok]   /v1/models → serving: ${served}"
        [[ -z "${model}" ]] && model="${served}"
    elif [[ "${code}" =~ ^2 ]]; then
        echo "  [warn] /v1/models → no models listed yet (still loading weights?)"
        failed=1
    else
        echo "  [FAIL] /v1/models → unreachable"
        failed=1
    fi

    if [[ -z "${model}" ]]; then
        echo "  [FAIL] no model available; aborting remaining checks"
        return 1
    fi

    # --- 3) tool-calls round-trip (validates --enable-auto-tool-choice + parser) --
    local tool_payload tool_code tool_name err_msg out_file
    tool_payload=$(
        cat <<EOF
{"model": "${model}", "max_tokens": 64,
 "messages": [{"role": "user", "content": "What is the weather in Paris? Use the tool to find out."}],
 "tools": [{"type": "function", "function": {
    "name": "get_weather",
    "description": "Get the current weather for a city",
    "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "City name"}}, "required": ["city"]}}}]
}
EOF
    )
    out_file=$(mktemp)
    tool_code=$(curl -sS -o "${out_file}" -w '%{http_code}' "${CURL_OPTS[@]}" "${auth_args[@]}" \
        -H "Content-Type: application/json" -X POST "${target_url}/chat/completions" \
        -d "${tool_payload}" 2>/dev/null)
    # Extract tool name from either standard OpenAI json or fallback to xml-style function tags
    tool_name=$(jq -r '.choices[0].message.tool_calls[0].function.name // empty' "${out_file}" 2>/dev/null)
    if [[ -z "${tool_name}" ]]; then
        tool_name=$(jq -r '.choices[0].message.content // empty' "${out_file}" 2>/dev/null | grep -oP '<function=\K[^>]+' | head -n1)
    fi
    err_msg=$(jq -r '.error.message // empty' "${out_file}" 2>/dev/null)
    rm -f "${out_file}"

    if [[ "${tool_code}" =~ ^2 && -n "${tool_name}" ]]; then
        echo "  [ok]   tool-calls → model invoked ${tool_name} (auto-tool-choice + parser active)"
    elif [[ "${tool_code}" =~ ^2 ]]; then
        echo "  [warn] tool-calls → HTTP 200 but no tool_calls returned (model declined; parser status uncertain)"
    else
        echo "  [FAIL] tool-calls → HTTP ${tool_code}: ${err_msg:0:160}"
        failed=1
    fi

    # --- 4) long-context ladder ----------------------------------------------------
    local tiers words
    IFS=',' read -ra tiers <<<"${VERIFY_TIERS}"
    for words in "${tiers[@]}"; do
        verify_long_context_tier "${type}" "${url}" "${model}" "${words}" || failed=1
    done

    return "${failed}"
}

# Function to display usage help and detailed command examples
function show_usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [COMMAND] [MODEL_NAME]

Multi-Endpoint LLM Server Management Utility.

OPTIONS:
  -h, --help                 Show this help message and exit.
  -j, --json                 Output raw, unformatted JSON responses from endpoints.
  -e, --endpoint <URL>       Specify a custom endpoint URL. Can be supplied multiple times.
      --use-case <case>      Filter/specify use case for llmfit recommendations.
                             Choices: general, coding, reasoning, chat, multimodal, embedding.
      --fit-filter <filter>  Filter by fit level (default: Runnable).
                             Choices: Runnable, Perfect, Good, Marginal, All.
      --runtime <rt>         Filter by inference runtime (default: Any).
                             Choices: Any, llama.cpp, vllm, MLX.
      --provider <prov>      Filter recommendations by model provider (e.g. Qwen, Meta).
      --limit <N>            Limit the number of returned recommendations (top N models).

COMMANDS:
  health | check             Check availability and health status across target endpoints.
  ping [model]               Send a test chat completion payload to verify inference.
  display | ls | list        List all downloaded/available models across all endpoints (Default action).
  recommend | llmfit         Query llmfit API server for hardware-matched model recommendations.
  ps | running               List currently loaded/running models in VRAM (Ollama endpoints only).
  pull | download <model>    Pull/download a model from registry (Ollama endpoints only).
  remove | rm | delete <model>  Remove/delete a model from local storage (Ollama endpoints only).
  verify | validate          Deep-verify OpenAI-compatible endpoints: /health, served model,
                             tool-calls round-trip, and a long-context ladder (VERIFY_TIERS).
                             Non-zero exit on failure (Ansible/CI friendly).

===============================================================================
                               USE CASES & EXAMPLES
===============================================================================

1. HEALTH CHECK (health / check)
   Use Case: Validate network connectivity and service status before submitting workloads.

   # Check health across all configured endpoints
   $ $(basename "$0") health

   # Verify health on a targeted server
   $ $(basename "$0") -e https://vllm-coder.llm-gb10.johnson.int/v1 check

2. CHAT INFERENCE PING (ping)
   Use Case: Send a minimal chat completion request to test end-to-end model response.

   # Ping vLLM endpoint (automatically discovers pre-loaded / lightest model if omitted)
   $ $(basename "$0") -e https://vllm-coder.llm-gb10.johnson.int/v1 ping

   # Ping with an explicit model target
   $ $(basename "$0") -e https://vllm-coder.llm-gb10.johnson.int/v1 ping qwen-coder

3. LISTING MODELS (display / ls / list)
   Use Case: Quick inventory audit to check what LLM weights are available.

   # List models across all default endpoints in standard formatted list
   $ $(basename "$0") display

   # List models and output the raw JSON response
   $ $(basename "$0") --json display

   # Check models on a specific host only
   $ $(basename "$0") -e https://ollama.llm-gb10.johnson.int list

4. LLMFIT RECOMMENDATIONS (recommend / llmfit)
   Use Case: Query llmfit API server to get hardware-tailored model recommendations.

   # Get recommendations with default filters (Runnable fit)
   $ $(basename "$0") recommend

   # Get top 10 coding models filtered by vllm runtime and Qwen provider
   $ $(basename "$0") --use-case coding --runtime vllm --provider Qwen --limit 10 recommend

   # Get raw JSON recommendations from a custom llmfit endpoint
   $ $(basename "$0") -e http://localhost:8787 --json llmfit

5. MONITORING RUNNING MODELS (ps / running)
   Use Case: Inspect active models residing in VRAM to debug memory load or OOM issues.

   # Query all active Ollama endpoints for currently running models in VRAM
   $ $(basename "$0") ps

   # Check active models on a custom Ollama host
   $ $(basename "$0") -e https://ollama.llm-rtx.johnson.int running

6. DOWNLOADING MODELS (pull / download)
   Use Case: Remote deployment of new model weights to local inference backends.

   # Download a 7B coder model to Ollama instances
   $ $(basename "$0") pull qwen2.5-coder:7b

   # Download a model to a specific target host
   $ $(basename "$0") -e https://ollama.llm-gb10.johnson.int download llama3.1:8b

7. DELETING MODELS (remove / rm / delete)
   Use Case: Reclaim GPU disk or VRAM space by removing large unused model weights.

   # Delete a specific model from Ollama backends
   $ $(basename "$0") remove qwen3-coder-next:q4_K_M

   # Remove a model from a single specified endpoint
   $ $(basename "$0") -e https://ollama.llm-gb10.johnson.int rm deepseek-r1:14b

8. DEEP VERIFICATION (verify / validate)
   Use Case: Post-deployment validation of vLLM endpoints — confirms the served model,
   that tool-calling is wired up, and that the context ceiling behaves as configured
   (e.g. a 128K window on qwen-coder).

   # Verify all configured endpoints (auto-discovers the model)
   $ ./llm-utils.sh verify

   # Verify a specific vLLM endpoint with an explicit model
   $ ./llm-utils.sh -e https://vllm-coder.llm-gb10.johnson.int/v1 verify qwen-coder

   # Scale the long-context ladder to the endpoint's window
   $ VERIFY_TIERS="5000,30000,100000" ./llm-utils.sh verify

===============================================================================
EOF
    exit 0
}

# -----------------------------------------------------------------------------
# 1. Parse Command Line Flags & Positional Arguments FIRST
# -----------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h | --help)
            show_usage
            ;;
        --json | -j)
            SHOW_RAW_JSON=true
            shift
            ;;
        --endpoint | -e)
            USER_LLM_ENDPOINTS+=("$2")
            shift 2
            ;;
        --use-case)
            USE_CASE="$2"
            shift 2
            ;;
        --fit-filter)
            FIT_FILTER="$2"
            shift 2
            ;;
        --runtime)
            RUNTIME="$2"
            shift 2
            ;;
        --provider)
            PROVIDER="$2"
            shift 2
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        *)
            if [[ "${ACTION_SET}" == "false" ]]; then
                ACTION="$1"
                ACTION_SET=true
            elif [[ -z "${MODEL_NAME}" ]]; then
                MODEL_NAME="$1"
            fi
            shift
            ;;
    esac
done

# Default to "display" action if none supplied
if [[ "${ACTION_SET}" == "false" ]]; then
    ACTION="display"
fi

# -----------------------------------------------------------------------------
# 2. Populate Target Endpoints Array AFTER parsing arguments
# -----------------------------------------------------------------------------
declare -A LLM_ENDPOINTS
if [[ ${#USER_LLM_ENDPOINTS[@]} -gt 0 ]]; then
    for ep in "${USER_LLM_ENDPOINTS[@]}"; do
        clean_ep="${ep%/}"
        if [[ "${clean_ep}" == *"llama"* ]]; then
            LLM_ENDPOINTS["${clean_ep}"]="llama"
        elif [[ "${clean_ep}" == *"/v1"* ]] || [[ "${clean_ep}" == *"vllm"* ]]; then
            LLM_ENDPOINTS["${clean_ep}"]="vllm"
        elif [[ "${clean_ep}" == *"llmfit"* ]] || [[ "${clean_ep}" == *":8787"* ]]; then
            USER_LLMFIT_ENDPOINTS+=("${clean_ep}")
        else
            LLM_ENDPOINTS["${clean_ep}"]="ollama"
        fi
    done
else
    for url in "${!DEFAULT_LLM_ENDPOINTS[@]}"; do
        clean_url="${url%/}"
        LLM_ENDPOINTS["${clean_url}"]="${DEFAULT_LLM_ENDPOINTS[$url]}"
    done
fi

# Populate LLMFIT_ENDPOINTS dictionary
declare -A LLMFIT_ENDPOINTS
if [[ ${#USER_LLMFIT_ENDPOINTS[@]} -gt 0 ]]; then
    for ep in "${USER_LLMFIT_ENDPOINTS[@]}"; do
        LLMFIT_ENDPOINTS["${ep}"]="llmfit"
    done
else
    for url in "${!DEFAULT_LLMFIT_ENDPOINTS[@]}"; do
        clean_url="${url%/}"
        LLMFIT_ENDPOINTS["${clean_url}"]="${DEFAULT_LLMFIT_ENDPOINTS[$url]}"
    done
fi

# -----------------------------------------------------------------------------
# 3. Execution Router
# -----------------------------------------------------------------------------
counter=1
case "${ACTION}" in
    health | check)
        for url in "${!LLM_ENDPOINTS[@]}"; do
            type="${LLM_ENDPOINTS[$url]}"
            echo "=========================================="
            echo " ${counter}. Health Check [${type^^}]: ${url}"
            echo "=========================================="

            if [[ "${type}" == "ollama" ]]; then
                readarray -t auth_args < <(get_ollama_auth_args)
                exec_curl "health" "${CURL_OPTS[@]}" "${auth_args[@]}" "${url}/api/version"
            elif [[ "${type}" == "vllm" ]]; then
                base_url="${url%/v1}"
                readarray -t auth_args < <(get_bearer_auth_args "vllm")
                exec_curl "health" "${CURL_OPTS[@]}" "${auth_args[@]}" "${base_url}/health"
            elif [[ "${type}" == "llama" ]]; then
                base_url="${url%/v1}"
                readarray -t auth_args < <(get_bearer_auth_args "llama")
                exec_curl "health" "${CURL_OPTS[@]}" "${auth_args[@]}" "${base_url}/health"
            fi
            ((counter++))
        done
        ;;

    recommend | llmfit)
        for url in "${!LLMFIT_ENDPOINTS[@]}"; do
            type="${LLMFIT_ENDPOINTS[$url]}"
            if [[ "${type}" == "llmfit" ]]; then
                echo "=========================================="
                echo " ${counter}. LLMFIT Recommendations: ${url}"
                [[ -n "${USE_CASE}" ]] && echo " Use Case: ${USE_CASE}"
                [[ -n "${FIT_FILTER}" ]] && echo " Fit Filter: ${FIT_FILTER}"
                [[ -n "${RUNTIME}" ]] && echo " Runtime: ${RUNTIME}"
                [[ -n "${PROVIDER}" ]] && echo " Provider: ${PROVIDER}"
                [[ -n "${LIMIT}" ]] && echo " Limit: Top ${LIMIT}"
                echo "=========================================="

                target_url="${url%/}/api/v1/models/top?"
                declare -a query_params=()
                [[ -n "${USE_CASE}" ]] && query_params+=("use_case=${USE_CASE}")
                [[ -n "${FIT_FILTER}" ]] && query_params+=("fit_filter=${FIT_FILTER}")
                [[ -n "${RUNTIME}" ]] && query_params+=("runtime=${RUNTIME}")
                [[ -n "${PROVIDER}" ]] && query_params+=("provider=${PROVIDER}")
                [[ -n "${LIMIT}" ]] && query_params+=("limit=${LIMIT}")

                # Join query parameters with '&'
                qs=""
                if [[ ${#query_params[@]} -gt 0 ]]; then
                    qs=$(IFS='&'; echo "${query_params[*]}")
                fi
                target_url="${target_url}${qs}"

                exec_curl "llmfit" "${CURL_OPTS[@]}" "${target_url}"
                ((counter++))
            fi
        done
        ;;

    ping)
        for url in "${!LLM_ENDPOINTS[@]}"; do
            type="${LLM_ENDPOINTS[$url]}"
            target_model="${MODEL_NAME}"

            if [[ -z "${target_model}" ]]; then
                target_model=$(discover_model "${type}" "${url}")
            fi

            if [[ -z "${target_model}" ]]; then
                echo "Error: Could not determine an available model on ${url}. Please specify one explicitly."
                continue
            fi

            echo "=========================================="
            echo " ${counter}. Chat Completion Ping [${type^^}]: ${url}"
            echo " Target Model: ${target_model}"
            echo "=========================================="

            if [[ "${type}" == "vllm" || "${type}" == "llama" ]]; then
                target_url="${url}"
                [[ "${target_url}" != *"/v1"* ]] && target_url="${target_url}/v1"
                readarray -t auth_args < <(get_bearer_auth_args "${type}")

                payload=$(
                    cat <<EOF
{
  "model": "${target_model}",
  "messages": [{"role": "user", "content": "ping"}],
  "max_tokens": 10
}
EOF
                )
                exec_curl "ping" "${CURL_OPTS[@]}" "${auth_args[@]}" -H "Content-Type: application/json" -X POST "${target_url}/chat/completions" -d "${payload}"

            elif [[ "${type}" == "ollama" ]]; then
                readarray -t auth_args < <(get_ollama_auth_args)

                payload=$(
                    cat <<EOF
{
  "model": "${target_model}",
  "prompt": "ping",
  "stream": false
}
EOF
                )
                exec_curl "ping" "${CURL_OPTS[@]}" "${auth_args[@]}" -H "Content-Type: application/json" -X POST "${url}/api/generate" -d "${payload}"
            fi
            ((counter++))
        done
        ;;

    display | ls | list)
        for url in "${!LLM_ENDPOINTS[@]}"; do
            type="${LLM_ENDPOINTS[$url]}"
            echo "=========================================="
            echo " ${counter}. Endpoint [${type^^}]: ${url}"
            echo "=========================================="

            if [[ "${type}" == "ollama" ]]; then
                readarray -t auth_args < <(get_ollama_auth_args)
                exec_curl "ollama" "${CURL_OPTS[@]}" "${auth_args[@]}" "${url}/api/tags"
            elif [[ "${type}" == "vllm" ]]; then
                target_url="${url}"
                [[ "${target_url}" != *"/v1"* ]] && target_url="${target_url}/v1"
                readarray -t auth_args < <(get_bearer_auth_args "vllm")
                exec_curl "vllm" "${CURL_OPTS[@]}" "${auth_args[@]}" "${target_url}/models"
            elif [[ "${type}" == "llama" ]]; then
                target_url="${url}"
                [[ "${target_url}" != *"/v1"* ]] && target_url="${target_url}/v1"
                readarray -t auth_args < <(get_bearer_auth_args "llama")
                exec_curl "llama" "${CURL_OPTS[@]}" "${auth_args[@]}" "${target_url}/models"
            fi
            ((counter++))
        done
        ;;

    ps | running)
        for url in "${!LLM_ENDPOINTS[@]}"; do
            type="${LLM_ENDPOINTS[$url]}"
            if [[ "${type}" == "ollama" ]]; then
                echo "=========================================="
                echo " ${counter}. Endpoint [OLLAMA]: ${url} (/api/ps)"
                echo "=========================================="
                readarray -t auth_args < <(get_ollama_auth_args)
                exec_curl "ollama" "${CURL_OPTS[@]}" "${auth_args[@]}" "${url}/api/ps"
                ((counter++))
            fi
        done
        ;;

    remove | rm | delete)
        if [[ -z "${MODEL_NAME}" ]]; then
            echo "Error: You must specify a model name to remove."
            echo "Usage: $0 [-e endpoint] remove <model_name>"
            exit 1
        fi

        for url in "${!LLM_ENDPOINTS[@]}"; do
            type="${LLM_ENDPOINTS[$url]}"
            echo "=========================================="
            echo " Target Endpoint [${type^^}]: ${url}"
            echo "=========================================="
            if [[ "${type}" == "ollama" ]]; then
                readarray -t auth_args < <(get_ollama_auth_args)
                exec_curl "raw" "${CURL_OPTS[@]}" -X DELETE "${auth_args[@]}" "${url}/api/delete" -d "{\"model\": \"${MODEL_NAME}\"}"
            else
                echo "Note: ${type^^} endpoints do not support dynamic REST deletion of model weights."
                echo ""
            fi
        done
        ;;

    pull | download)
        if [[ -z "${MODEL_NAME}" ]]; then
            echo "Error: You must specify a model name to pull."
            echo "Usage: $0 [-e endpoint] pull <model_name>"
            exit 1
        fi

        for url in "${!LLM_ENDPOINTS[@]}"; do
            type="${LLM_ENDPOINTS[$url]}"
            if [[ "${type}" == "ollama" ]]; then
                echo "=========================================="
                echo " Pulling '${MODEL_NAME}' to ${url}"
                echo "=========================================="
                readarray -t auth_args < <(get_ollama_auth_args)
                exec_curl "raw" "${CURL_OPTS[@]}" -X POST "${auth_args[@]}" "${url}/api/pull" -d "{\"name\": \"${MODEL_NAME}\", \"stream\": false}"
            fi
        done
        ;;

    verify | validate)
        VERIFY_EXIT=0
        for url in "${!LLM_ENDPOINTS[@]}"; do
            type="${LLM_ENDPOINTS[$url]}"
            echo "=========================================="
            echo " ${counter}. VERIFY [${type^^}]: ${url}"
            echo "=========================================="
            if [[ "${type}" == "vllm" || "${type}" == "llama" ]]; then
                target_model="${MODEL_NAME}"
                [[ -z "${target_model}" ]] && target_model=$(discover_model "${type}" "${url}")
                if [[ -z "${target_model}" ]]; then
                    echo "  [FAIL] could not discover a model; specify one explicitly"
                    VERIFY_EXIT=1
                else
                    echo "  Target Model: ${target_model}"
                    verify_openai_endpoint "${type}" "${url}" "${target_model}" || VERIFY_EXIT=1
                fi
            else
                echo "  [skip] 'verify' targets OpenAI-compatible endpoints (vLLM/Llama)."
                echo "         Ollama: use 'health' / 'ping' / 'ps' instead."
            fi
            echo ""
            ((counter++))
        done

        echo "=========================================="
        if [[ "${VERIFY_EXIT}" -eq 0 ]]; then
            echo " VERIFY RESULT: ALL CHECKS PASSED"
        else
            echo " VERIFY RESULT: FAILURES DETECTED — see [FAIL] lines above"
            echo "=========================================="
            exit 1
        fi
        echo "=========================================="
        exit 0
        ;;

    *)
        echo "Unknown command: ${ACTION}"
        echo "Run '$0 --help' for usage and examples."
        exit 1
        ;;
esac
