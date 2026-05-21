#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
MODEL_DIR="$ROOT/models/Qwen3-TTS-12Hz-0.6B-Base-8bit"
BASE_URL="https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit/resolve/main"

mkdir -p "$MODEL_DIR/speech_tokenizer"

# Download one model file with resume/retry support so large weights survive flaky links.
download_file() {
  rel="$1"
  target="$MODEL_DIR/$rel"
  partial="$target.partial"
  url="$BASE_URL/$rel"

  mkdir -p "$(dirname "$target")"
  if [ -s "$target" ]; then
    echo "exists $rel"
    return 0
  fi

  echo "download $rel"
  # Keep partial files separate until curl exits successfully.
  curl -4 --http1.1 \
    --location \
    --fail \
    --continue-at - \
    --retry 30 \
    --retry-delay 5 \
    --retry-all-errors \
    --connect-timeout 30 \
    --speed-limit 1024 \
    --speed-time 120 \
    --output "$partial" \
    "$url"
  mv "$partial" "$target"
}

# Keep this list explicit; it doubles as documentation of the expected model layout.
download_file ".gitattributes"
download_file "README.md"
download_file "config.json"
download_file "generation_config.json"
download_file "merges.txt"
download_file "model.safetensors.index.json"
download_file "preprocessor_config.json"
download_file "tokenizer_config.json"
download_file "vocab.json"
download_file "speech_tokenizer/config.json"
download_file "speech_tokenizer/configuration.json"
download_file "speech_tokenizer/preprocessor_config.json"
download_file "speech_tokenizer/model.safetensors"
download_file "model.safetensors"

echo "done $MODEL_DIR"
