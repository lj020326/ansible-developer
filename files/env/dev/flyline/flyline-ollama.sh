#!/usr/bin/env bash

PROMPT="$1"
#ENDPOINT="https://ollama.llm-rtx.johnson.int/v1/chat/completions"
ENDPOINT="${OLLAM_API_URL:-https://ollama.llm-rtx.johnson.int/api/chat}"
AUTH_HEADER="Authorization: Basic ${OLLAMA_API_KEY}"
MODEL="qwen3-coder:30b"

SYSTEM_PROMPT="You are a shell command assistant. Translate the prompt into a valid Bash command. Return ONLY a valid raw JSON array containing objects with keys 'command' and 'description'. Do not use markdown backticks. Example: [{\"command\": \"find /var/log -mtime -1\", \"description\": \"Find files modified in last 24 hours\"}]"

PAYLOAD=$(jq -n \
  --arg model "$MODEL" \
  --arg sys "$SYSTEM_PROMPT" \
  --arg user "$PROMPT" \
  '{
    model: $model,
    stream: false,
    format: "json",
    messages: [
      {role: "system", content: $sys},
      {role: "user", content: $user}
    ]
  }')

RESPONSE=$(curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d "$PAYLOAD")

# Extract message content safely
echo "$RESPONSE" | jq -r '.message.content // empty'
