#!/bin/bash
set -x
cd /Users/bcb/Documents/ClarityOmega/IterBrow/hyperon-src-debug
export CARGO_HOME="$(pwd)/cargo_home_debug"
LOG=/tmp/trie_test2.log
: > "$LOG"
{
  echo "=== atom_index_survives_key_ids_above_max_expression_size (needs test fn added) ==="
  cargo test -p hyperon-space --all-features atom_index_survives_key_ids_above_max_expression_size 2>&1
  echo "EXIT1=$?"
  echo "=== atom_index_iter_enumerates_all_atoms_above_key_id_threshold ==="
  cargo test -p hyperon-space --all-features atom_index_iter_enumerates_all_atoms_above_key_id_threshold 2>&1
  echo "EXIT2=$?"
} >> "$LOG" 2>&1
echo TRIE_TEST2_DONE >> "$LOG"
