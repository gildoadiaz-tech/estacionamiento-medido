#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Instalando Estacionamiento Medido..."

python3 -m venv venv
source venv/bin/activate

echo "📦 Instalando dependencias..."
pip install -q -r requirements.txt

echo "🗄️  Inicializando base de datos..."
python seed.py

echo ""
echo "✅ Instalación completa!"
echo ""
echo "Para iniciar:"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "Abrir: http://localhost:8000"
