# LiveCut MVP

Protótipo local de um site de cortes automáticos de lives, inspirado no fluxo de ferramentas como OpusClip. Não copia código ou serviços proprietários.

## O que faz
- Recebe links públicos de YouTube e Twitch via `yt-dlp`.
- Analisa volume médio/picos de áudio em janelas de 5 segundos.
- Opcionalmente transcreve fala com `faster-whisper` (modelo `tiny`, `base` ou `small`).
- Combina os sinais em uma pontuação heurística e propõe trechos candidatos.
- Permite exportar cada candidato em MP4 vertical 9:16.

## O que ainda não faz
- Não compreende o jogo visualmente nem garante que um pico seja uma jogada boa.
- Não gera legendas embutidas, zoom dinâmico, rastreamento de rosto, templates de marca ou publicação automática.
- Não processa URLs que exijam login, sejam privadas, estejam protegidas por DRM ou não estejam acessíveis.
- A pontuação é experimental; revise todos os cortes.

## Requisitos
- Python 3.10 ou 3.11 recomendado.
- FFmpeg e FFprobe instalados e no PATH.
- Internet para baixar VODs públicos e baixar o modelo Whisper na primeira execução.
- Espaço em disco: lives longas podem ocupar muitos GB.

## Instalação — Windows
1. Instale Python 3.11 e marque **Add Python to PATH**.
2. Instale FFmpeg e confirme no terminal:
   - `ffmpeg -version`
   - `ffprobe -version`
3. Extraia o ZIP para uma pasta.
4. Abra o Prompt de Comando nessa pasta e rode:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

5. O navegador abrirá o site local. Se não abrir, acesse `http://localhost:8501`.

## Dicas para seu PC (i3-10100F, GTX 1650 4 GB, 16 GB RAM)
- Comece com Whisper `tiny` e VODs de 20–60 minutos.
- Para economizar espaço, apague a pasta `workspace` quando terminar.
- A análise de áudio usa CPU; a transcrição também está configurada para CPU/int8 para reduzir problemas de compatibilidade.
- Exportar vários cortes consome CPU. Exporte um de cada vez.

## Próximas melhorias
1. Legendas SRT e legendas embutidas com estilo.
2. Sinais de jogo específicos: kills, vitórias, mudanças de cena e HUD, quando detectáveis.
3. Linha do tempo com prévia e edição dos tempos de início/fim.
4. Perfil de canal: palavras/reações e duração preferidas.
5. Melhor ranking com avaliação dos cortes aprovados/rejeitados.
6. Deploy remoto com fila de trabalhos, autenticação e armazenamento — não incluído neste MVP local.
