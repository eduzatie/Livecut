LiveCut MVP - guia rápido

1. Instale Python 3.10 ou 3.11.
2. Instale FFmpeg e confirme que ffmpeg e ffprobe funcionam no terminal.
3. Extraia o arquivo ZIP.
4. Abra o Prompt de Comando na pasta extraída e execute:

python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py

5. Abra http://localhost:8501 se o navegador não abrir automaticamente.
6. Cole o link público de um VOD do YouTube/Twitch e clique em Analisar live.

Comece com um VOD curto e Whisper tiny. O projeto ainda é experimental e os cortes precisam de revisão.
