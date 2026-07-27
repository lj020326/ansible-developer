#!/usr/bin/env bash

# Option Flags
SHOW_RAW_JSON=false
ACTION="display"
MODEL_NAME=""
declare -a USER_ENDPOINTS=()

# Define Default Endpoints using Bash Associative Array
declare -A DEFAULT_ENDPOINTS=(
  ["${OLLAMA_API_URL:-https://ollama.llm-rtx.johnson.int}"]="ollama"
  ["${VLLM_API_URL:-https://vllm.llm-gb10.johnson.int/v1}"]="vllm"
  ["${LLAMA_API_URL:-https://llama.llm-rtx.johnson.int/v1}"]="llama"
  ["https://ollama.llm-gb10.johnson.int"]="ollama"
  ["https://llama.llm-gb10.johnson.int"]="llama"
)

# Populate Active Endpoints
declare -A ENDPOINTS
if [[ ${#USER_ENDPOINTS[@]} -gt 0 ]]; then
  for ep in "${USER_ENDPOINTS[@]}"; do
    clean_ep="${ep%/}"
    if [[ "${clean_ep}" == *"llama"* ]]; then
      ENDPOINTS["${clean_ep}"]="llama"
    elif [[ "${clean_ep}" == *"/v1"* ]] || [[ "${clean_ep}" == *"vllm"* ]]; then
      ENDPOINTS["${clean_ep}"]="vllm"
    else
      ENDPOINTS["${clean_ep}"]="ollama"
    fi
  done
else
  for url in "${!DEFAULT_ENDPOINTS[@]}"; do
    clean_url="${url%/}"
    ENDPOINTS["${clean_url}"]="${DEFAULT_ENDPOINTS[$url]}"
  done
fi

# Curl default options
CURL_OPTS="-sS --connect-timeout 5 --max-time 15"

function execute() {
  local endpoint_type="$1"
  shift
  local command_str="${*}"

  # Mask sensitive credentials in stdout log output
  local masked_cmd
  masked_cmd=$(echo "${command_str}" | sed -E \
    -e 's/Authorization: Bearer [^ '\''"]+/Authorization: Bearer [REDACTED]/g' \
    -e 's/Authorization: Basic [^ '\''"]+/Authorization: Basic [REDACTED]/g' \
    -e 's/-u '\''[^'\'']+'\''/-u '\''[REDACTED]'\''/g')

  echo ">>> Running: ${masked_cmd}"

  local output
  output=$(eval "${command_str}" 2>&1)
  local RETURN_STATUS=$?

  if [[ $RETURN_STATUS -ne 0 ]]; then
    echo "ERROR (exit status ${RETURN_STATUS}):"
    echo "${output}"
  else
    if echo "${output}" | jq . >/dev/null 2>&1; then
      if [[ "${SHOW_RAW_JSON}" == "true" ]]; then
        echo "${output}" | jq
      else
        # Extract model names by endpoint type
        case "${endpoint_type}" in
          ollama)
            echo "${output}" | jq -r '.models[]?.name // empty' | sed 's/^/ - /'
            ;;
          vllm|llama)
            echo "${output}" | jq -r '.data[]?.id // empty' | sed 's/^/ - /'
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
  echo ""
}

# Helper for Bearer Token Auth Headers (vLLM and Llama)
function get_bearer_auth_header() {
  local key="${LLAMA_API_KEY:-${VLLM_API_KEY}}"
  if [[ -n "${key}" ]]; then
    echo "-H 'Authorization: Bearer ${key}'"
  fi
}

# Helper for Ollama Basic Auth Header / Option
function get_ollama_auth_param() {
  if [[ -n "${OLLAMA_API_KEY}" ]]; then
    # If the key contains a colon, it's raw 'user:password'
    if [[ "${OLLAMA_API_KEY}" == *":"* ]]; then
      # Raw 'user:password' supplied
      echo "-u \"${OLLAMA_API_KEY}\""
    else
      # Pre-encoded Base64 key supplied
      echo "-H \"Authorization: Basic ${OLLAMA_API_KEY}\""
    fi
  fi
}

# Parse command line flags & positional arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json|-j)
      SHOW_RAW_JSON=true
      shift
      ;;
    --endpoint|-e)
      USER_ENDPOINTS+=("$2")
      shift 2
      ;;
    *)
      if [[ -z "${ACTION_SET}" ]]; then
        ACTION="$1"
        ACTION_SET=true
      elif [[ -z "${MODEL_NAME}" ]]; then
        MODEL_NAME="$1"
      fi
      shift
      ;;
  esac
done

# Main Command Router
counter=1
case "${ACTION}" in
  display|ls|list)
    for url in "${!ENDPOINTS[@]}"; do
      type="${ENDPOINTS[$url]}"
      echo "=========================================="
      echo " ${counter}. Endpoint [${type^^}]: ${url}"
      echo "=========================================="

      if [[ "${type}" == "ollama" ]]; then
        execute "ollama" "curl ${CURL_OPTS} $(get_ollama_auth_param) '${url}/api/tags'"
      elif [[ "${type}" == "vllm" ]]; then
        # Handle cases where url might already end in /v1 or not
        target_url="${url}"
        [[ "${target_url}" != *"/v1"* ]] && target_url="${target_url}/v1"
        execute "vllm" "curl ${CURL_OPTS} $(get_bearer_auth_header) '${target_url}/models'"
      elif [[ "${type}" == "llama" ]]; then
        target_url="${url}"
        [[ "${target_url}" != *"/v1"* ]] && target_url="${target_url}/v1"
        execute "llama" "curl ${CURL_OPTS} $(get_bearer_auth_header) '${target_url}/models'"
      fi
      ((counter++))
    done
    ;;

  ps|running)
    for url in "${!ENDPOINTS[@]}"; do
      type="${ENDPOINTS[$url]}"
      if [[ "${type}" == "ollama" ]]; then
        echo "=========================================="
        echo " ${counter}. Endpoint [OLLAMA]: ${url} (/api/ps)"
        echo "=========================================="
        execute "ollama" "curl ${CURL_OPTS} $(get_ollama_auth_param) '${url}/api/ps'"
        ((counter++))
      fi
    done
    ;;

  remove|rm|delete)
    if [[ -z "${MODEL_NAME}" ]]; then
      echo "Error: You must specify a model name to remove."
      echo "Usage: $0 remove <model_name>"
      exit 1
    fi

    for url in "${!ENDPOINTS[@]}"; do
      type="${ENDPOINTS[$url]}"
      echo "=========================================="
      echo " Target Endpoint [${type^^}]: ${url}"
      echo "=========================================="
      if [[ "${type}" == "ollama" ]]; then
        execute "raw" "curl ${CURL_OPTS} -X DELETE $(get_ollama_auth_param) '${url}/api/delete' -d '{\"model\": \"${MODEL_NAME}\"}'"
      else
        echo "Note: ${type^^} endpoints do not support dynamic REST deletion of model weights."
        echo ""
      fi
    done
    ;;

  pull|download)
    if [[ -z "${MODEL_NAME}" ]]; then
      echo "Error: You must specify a model name to pull."
      echo "Usage: $0 pull <model_name>"
      exit 1
    fi

    for url in "${!ENDPOINTS[@]}"; do
      type="${ENDPOINTS[$url]}"
      if [[ "${type}" == "ollama" ]]; then
        echo "=========================================="
        echo " Pulling '${MODEL_NAME}' to ${url}"
        echo "=========================================="
        execute "raw" "curl ${CURL_OPTS} -X POST $(get_ollama_auth_param) '${url}/api/pull' -d '{\"name\": \"${MODEL_NAME}\", \"stream\": false}'"
      fi
    done
    ;;

  *)
    echo "Unknown command: ${ACTION}"
    echo "Usage: $0 [-j|--json] [-e <endpoint>] {display|ps|remove <model>|pull <model>}"
    exit 1
    ;;
esac
