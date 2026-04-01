#!/bin/bash
# ==========================================
# AVVIO SERVER SOPOTFY LOCALE + TUNNEL
# ==========================================

echo "🚀 [1/3] Installazione/Verifica dipendenze FastAPI..."
cd backend
python3 -m pip install -r requirements.txt &> /dev/null

echo "🚀 [2/3] Avvio di Sopotfy Server (Log salvati in backend/server.log)..."
# Avvia fastapi in background e salva i log in un file
uvicorn main:app --host 0.0.0.0 --port 10000 > server.log 2>&1 &
SERVER_PID=$!

echo "⏳ Attendo 3 secondi per il riscaldamento del server..."
sleep 3

echo "🌐 [3/3] Avvio Tunnel Localtunnel (Inoltro al Cellulare)..."
echo "=========================================================="
echo "⚠️  IMPORTANTE: Lascia aperta questa finestra del terminale!"
echo "❌  Per spegnere tutto premi: CTRL + C"
echo "=========================================================="

# Il parametro sopotfy-sossio fissa l'URL per non cambiarlo mai
# Il parametro host bypassa i bug di connessione rifiutata
npx localtunnel --port 10000 --subdomain sopotfy-sossio --host http://localtunnel.me

echo ""
echo "🛑 Spegnimento del Server in corso..."
kill $SERVER_PID
echo "✅ Server spento con successo. A presto!"
