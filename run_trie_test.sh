#!/bin/bash
set -x
cd /Users/bcb/Documents/ClarityOmega/IterBrow/hyperon-src-debug
export CARGO_HOME="$(pwd)/cargo_home_debug"
LOG=/tmp/trie_test.log
: > "$LOG"
{
  echo "=== cargo test -p hyperon-space trie_key_value_roundtrip ==="
  cargo test -p hyperon-space trie_key_value_roundtrip_above_max_expression_size 2>&1
  echo "EXIT_CODE=$?"
} >> "$LOG" 2>&1
echo TRIE_TEST_DONE >> "$LOG"
