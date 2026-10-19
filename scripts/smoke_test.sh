#!/bin/bash
# Smoke test del binario empaquetado con PyInstaller.
# Arranca la aplicacion, comprueba que sigue viva tras N segundos y la cierra.
# Uso:  bash scripts/smoke_test.sh <ruta-del-binario> [segundos]
# En CI se ejecuta con QT_QPA_PLATFORM=offscreen (sin display).
set -u

BIN="${1:?uso: smoke_test.sh <binario> [segundos]}"
WAIT="${2:-20}"

if [ ! -e "$BIN" ]; then
    echo "ERROR: no existe el binario: $BIN"
    exit 1
fi

LOG="$(mktemp)"
QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" "$BIN" >"$LOG" 2>&1 &
PID=$!

for _ in $(seq 1 "$WAIT"); do
    sleep 1
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "CRASH: el binario termino antes de ${WAIT}s"
        cat "$LOG"
        rm -f "$LOG"
        exit 1
    fi
done

echo "OK: $BIN sigue vivo tras ${WAIT}s (se cierra el proceso de prueba)"
kill "$PID" 2>/dev/null || true
sleep 2
rm -f "$LOG"
exit 0
