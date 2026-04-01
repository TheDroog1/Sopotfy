#!/bin/bash
# ==========================================
# AVVIO SERVER SOPOTFY LOCALE + CLOUDFLARE
# ==========================================

echo "🚀 [1/3] Pulizia processi precedenti..."
pkill -9 -f uvicorn 2>/dev/null
pkill -f cloudflared 2>/dev/null

echo "🚀 [2/3] Avvio di Sopotfy Turbo (Log: backend/server.log)..."
cd backend
# Avvia fastapi con il motore Turbo Homebrew
uvicorn main:app --host 0.0.0.0 --port 10000 > server.log 2>&1 &
SERVER_PID=$!

echo "⏳ Attendo il riscaldamento del server..."
sleep 3

echo "🌐 [3/3] Avvio Tunnel Cloudflare (Ponte Diretto Telefono)..."
echo "=========================================================="
echo "⚠️  IMPORTANTE: Lascia aperta questa finestra!"
echo "❌  Per spegnere tutto premi: CTRL + C"
echo "=========================================================="

# Avvia cloudflared e mostra l'URL all'utente
cloudflared tunnel --url http://localhost:10000

echo ""
echo "🛑 Spegnimento del Server in corso..."
kill $SERVER_PID
echo "✅ Sistemato. A presto!"
