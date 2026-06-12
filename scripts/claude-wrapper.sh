#!/usr/bin/env bash
# Multi-provider Claude router
# Place at /usr/local/bin/claude (takes priority over /usr/bin/claude)
# Supports: deepseek-v4-flash, deepseek-v4-pro, claude-*, glm-*, qwen-*, minimax-*
source /etc/claude-providers.env 2>/dev/null || true

MODEL=""
MODEL_NEXT=""
MODEL_IDX=-1
IDX=0
for arg in "$@"; do
    if [ "$MODEL_NEXT" = "1" ]; then
        MODEL="$arg"
        MODEL_IDX=$IDX
        MODEL_NEXT=""
    fi
    if [ "$arg" = "--model" ]; then
        MODEL_NEXT="1"
    fi
    IDX=$((IDX+1))
done

# Expand shorthand aliases to canonical model names
case "$MODEL" in
    ds|deepseek|flash)   MODEL="deepseek-v4-flash" ;;
    pro|deepseek-pro)    MODEL="deepseek-v4-pro" ;;
    cl|claude|sonnet)    MODEL="claude-sonnet-4-6" ;;
    opus)                MODEL="claude-opus-4-8" ;;
    haiku)               MODEL="claude-haiku-4-5-20251001" ;;
esac

# Rebuild args with expanded model name
declare -a NEWARGS=()
IDX=0
for arg in "$@"; do
    if [ "$IDX" = "$MODEL_IDX" ]; then
        NEWARGS+=("$MODEL")
    else
        NEWARGS+=("$arg")
    fi
    IDX=$((IDX+1))
done

# Route to correct provider based on model name
case "$MODEL" in
    claude-*)
        # Real Anthropic — unset DeepSeek overrides, uses OAuth (claude auth login)
        unset ANTHROPIC_BASE_URL
        unset ANTHROPIC_API_KEY
        ;;
    deepseek-*)
        export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
        export ANTHROPIC_API_KEY="$DEEPSEEK_API_KEY"
        ;;
    # ── Uncomment when you have the API key in /etc/claude-providers.env ──
    # glm-*|chatglm-*)
    #     export ANTHROPIC_BASE_URL="https://open.bigmodel.cn/api/paas/v4/"
    #     export ANTHROPIC_API_KEY="$GLM_API_KEY" ;;
    # qwen-*)
    #     export ANTHROPIC_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
    #     export ANTHROPIC_API_KEY="$QWEN_API_KEY" ;;
    # minimax-*)
    #     export ANTHROPIC_BASE_URL="https://api.minimax.chat/v1"
    #     export ANTHROPIC_API_KEY="$MINIMAX_API_KEY" ;;
    *)
        # Default: keep inherited env vars
        ;;
esac

exec /usr/bin/claude "${NEWARGS[@]}"
