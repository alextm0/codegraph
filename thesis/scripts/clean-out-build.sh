#!/usr/bin/env bash
# Remove LaTeX auxiliary files from the IDE output directory (../out).
# Run after a failed/interrupted build if you see:
#   "File ended while scanning use of \@newl@bel" or "Runaway argument" on \begin{document}
#   "File ended while scanning use of \contentsline" at \tableofcontents
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/../out"
if [[ ! -d "$OUT" ]]; then
  echo "No output directory at $OUT" >&2
  exit 1
fi
rm -f "$OUT"/main.{aux,out,toc,lof,lot,loa,nav,snm,vrb,fls,fdb_latexmk,synctex.gz}
echo "Cleaned auxiliary files in $OUT"
