
# Flyline configuration

## Using local ollama

Flyline’s **Agent Mode** works by taking the natural language prompt you type after your trigger prefix (e.g., `ai: list files older than 3 days`) and piping or passing it to a CLI command that returns JSON or plain text shell suggestions.

Since your Ollama instance at `[https://ollama.llm-rtx.johnson.int](https://ollama.llm-rtx.johnson.int)` is secured with Basic Auth, you can hook Flyline directly into your `qwen3-coder:30b` (or `qwen2.5-coder:7b`) model using a lightweight `curl` + `jq` wrapper.

---

### Step 1: Create a Lightweight Shell Helper Script

Create a script at `~/.local/bin/flyline-ollama` (or anywhere in your PATH) to bridge Flyline with your Ollama endpoint:

```bash
mkdir -p ~/.local/bin
cat << 'EOF' > ~/.local/bin/flyline-ollama
#!/usr/bin/env bash

PROMPT="$1"
ENDPOINT="https://ollama.llm-rtx.johnson.int/v1/chat/completions"
AUTH_HEADER="Authorization: Basic ${OLLAMA_API_KEY}"
MODEL="qwen3-coder:30b"

SYSTEM_PROMPT="You are a shell assistant. Convert the user's request into a valid Bash command. Return ONLY a JSON array containing objects with 'command' and 'description' keys. Example: [{\"command\": \"ls -la\", \"description\": \"List all files in long format including hidden files\"}]"

PAYLOAD=$(jq -n \
  --arg model "$MODEL" \
  --arg sys "$SYSTEM_PROMPT" \
  --arg user "$PROMPT" \
  '{
    model: $model,
    messages: [
      {role: "system", content: $sys},
      {role: "user", content: $user}
    ],
    temperature: 0.1,
    response_format: {type: "json_object"}
  }')

curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d "$PAYLOAD" | jq -r '.choices[0].message.content'
EOF

chmod +x ~/.local/bin/flyline-ollama

```

---

### Step 2: Configure Flyline Agent Mode

Now tell Flyline to use your new script when you type your trigger prefix (e.g., `ai: `):

```bash
flyline set-agent-mode \
  --trigger-prefix 'ai: ' \
  --command '$HOME/.local/bin/flyline-ollama'
```

> **Tip:** To make this persistent across terminal sessions, add that `flyline set-agent-mode` command to your `~/.zshrc` or `~/.bashrc`.

---

### Step 3: Test It Out 🧪

At your shell prompt, type your trigger prefix followed by a request:

```shell
ai: find all log files in /var/log modified in the last 24 hours

```

Flyline will query your local `qwen3-coder:30b` model and render the suggested command with its inline tooltip right at your prompt!
