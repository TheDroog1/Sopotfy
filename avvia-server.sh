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

# Avvia cloudflared in background, salva l'URL e lo mostra all'utente
cloudflared tunnel --url http://localhost:10000 > cf.txt 2>&1 &
CF_PID=$!

echo "📡 Cloudflare in ascolto... l'app si collegherà tra 10 secondi."
echo "🔗 Puoi anche monitorare l'URL qui: cat backend/cf.txt | grep trycloudflare"
echo "=========================================================="

# Mantieni lo script attivo
wait $SERVER_PID $CF_PID

echo ""
echo "🛑 Spegnimento del Server in corso..."
kill $SERVER_PID $CF_PID
echo "✅ Sistemato. A presto!"
