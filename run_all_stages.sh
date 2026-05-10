#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="cefr_stages"
OUTPUT_DIR="sampled_output"
SEED=42

for i in $(seq -w 0 30); do
    echo "=== stage_${i} ==="
    python3 sample_stage_vocab.py \
        --input-dir "$INPUT_DIR" \
        --stage "stage_${i}" \
        --output-dir "$OUTPUT_DIR" \
        --seed "$SEED"
    echo
done

echo "Done. All outputs in ${OUTPUT_DIR}/"
