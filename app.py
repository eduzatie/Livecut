import os, re, json, subprocess, tempfile, shutil
from pathlib import Path
import streamlit as st

APP_DIR = Path(__file__).parent
WORK_DIR = APP_DIR / "workspace"
WORK_DIR.mkdir(exist_ok=True)
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov"}

st.set_page_config(page_title="LiveCut — cortes automáticos", page_icon="✂️", layout="wide")
st.title("✂️ LiveCut")
st.caption("MVP local para encontrar momentos promissores em lives e exportar cortes verticais.")
st.info("Esta versão é um protótipo local: usa sinais de áudio + transcrição opcional para sugerir trechos. Revise os cortes antes de publicar.")

with st.sidebar:
    st.header("Configurações")
    clip_len = st.slider("Duração-alvo de cada corte (segundos)", 15, 90, 35, 5)
    num_clips = st.slider("Quantidade de cortes candidatos", 3, 15, 8)
    use_transcription = st.checkbox("Transcrever fala para melhorar os candidatos (mais lento)", value=True)
    model_size = st.selectbox("Modelo Whisper", ["tiny", "base", "small"], index=0, help="tiny é o mais leve; small tende a transcrever melhor e exige mais recursos.")
    st.caption("Hardware-alvo: CPU de entrada, 16 GB RAM e GPU opcional. O MVP não exige GPU.")

url = st.text_input("Link público de YouTube ou Twitch", placeholder="https://www.youtube.com/watch?v=... ou https://www.twitch.tv/videos/...")
st.caption("Use apenas vídeos aos quais você tem direito de acesso e permissão para baixar/editar. Lives privadas, protegidas ou inacessíveis não serão processadas.")
run = st.button("Analisar live", type="primary", use_container_width=True)

def have(cmd):
    return shutil.which(cmd) is not None

def run_cmd(args, timeout=None):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "Comando falhou")[-3500:])
    return p.stdout

def get_duration(path):
    out = run_cmd(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)])
    return float(out.strip())

def download_video(url, outdir):
    # Restrict to public YouTube/Twitch URLs; yt-dlp handles supported URL formats.
    if not re.match(r"^https?://", url.strip(), re.I):
        raise ValueError("Cole um link começando com http:// ou https://.")
    low = url.lower()
    if not any(host in low for host in ("youtube.com", "youtu.be", "twitch.tv")):
        raise ValueError("Este MVP aceita links de YouTube e Twitch.")
    outtmpl = str(outdir / "source.%(ext)s")
    run_cmd(["yt-dlp", "--no-playlist", "--restrict-filenames", "-f", "bv*[height<=1080]+ba/b[height<=1080]/best", "--merge-output-format", "mp4", "-o", outtmpl, url], timeout=60*60*4)
    candidates = [p for p in outdir.glob("source.*") if p.suffix.lower() in VIDEO_EXTS]
    if not candidates:
        candidates = [p for p in outdir.glob("source.*") if p.is_file() and p.suffix.lower() not in {".json", ".part", ".ytdl"}]
    if not candidates:
        raise RuntimeError("O download terminou, mas não encontrei o arquivo de vídeo. Veja se o link é público e acessível.")
    return max(candidates, key=lambda p:p.stat().st_size)

def transcribe(path, model_size):
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise RuntimeError("Falta instalar faster-whisper. Rode: pip install -r requirements.txt") from e
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(path), vad_filter=True, word_timestamps=False)
    return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()} for s in segments if s.text.strip()]

def audio_scores(path, duration, step=5):
    # Samples audio loudness in small windows; peaks can indicate reactions/action, but are not proof of a good moment.
    scores=[]
    for start in range(0, int(duration), step):
        length=min(step, duration-start)
        if length <= 0: continue
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-ss",str(start),"-t",str(length),"-i",str(path),"-vn","-af","volumedetect","-f","null","-"]
        p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        m=re.search(r"mean_volume:\s*(-?[\d.]+) dB",p.stderr)
        peak=re.search(r"max_volume:\s*(-?[\d.]+) dB",p.stderr)
        mean=float(m.group(1)) if m else -60
        maxv=float(peak.group(1)) if peak else -60
        scores.append({"start":start,"end":start+length,"mean":mean,"peak":maxv})
    if not scores: return []
    means=[x["mean"] for x in scores]
    peaks=[x["peak"] for x in scores]
    def norm(v, vals):
        lo=min(vals); hi=max(vals)
        return 0 if hi-lo<0.1 else (v-lo)/(hi-lo)
    for s in scores:
        s["score"]=0.55*norm(s["mean"],means)+0.45*norm(s["peak"],peaks)
    return scores

def propose_clips(duration, clip_len, n, scores, transcript):
    if duration <= clip_len:
        return [{"start":0,"end":duration,"score":1.0,"reason":"Vídeo curto; candidato completo."}]
    # Build a simple timeline score combining audio energy and speech density/keywords.
    words = ["caralho","nossa","meu deus","inacreditável","insano","boa","nice","ace","clutch","kill","matei","matou","ganhei","vitória","kkkk","hahaha","wtf"]
    step = 5
    windows=[]
    for s in scores:
        text=" ".join(seg["text"].lower() for seg in transcript if seg["start"] < s["end"] and seg["end"] > s["start"])
        keyword_bonus=min(0.35, sum(text.count(w) for w in words)*0.07)
        speech_bonus=0.12 if text.strip() else 0
        windows.append({"start":s["start"],"end":s["end"],"score":s["score"]+keyword_bonus+speech_bonus,"text":text})
    candidates=[]
    stride=max(5, clip_len//3)
    for start in range(0, max(1,int(duration-clip_len)+1), stride):
        end=min(duration,start+clip_len)
        relevant=[w for w in windows if w["start"] < end and w["end"] > start]
        if not relevant: continue
        score=sum(w["score"] for w in relevant)/len(relevant)
        text=" ".join(w["text"] for w in relevant).strip()
        reason="Pico de áudio"
        if text: reason="Atividade de áudio + fala detectada"
        if any(k in text for k in words): reason="Fala/reação potencial + atividade de áudio"
        candidates.append({"start":float(start),"end":float(end),"score":score,"reason":reason,"text":text[:500]})
    candidates.sort(key=lambda c:c["score"], reverse=True)
    chosen=[]
    for c in candidates:
        if all(abs(c["start"]-x["start"]) >= clip_len*0.7 for x in chosen):
            chosen.append(c)
        if len(chosen)>=n: break
    return sorted(chosen,key=lambda c:c["start"])

def fmt_time(seconds):
    seconds=int(seconds)
    return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"

def export_clip(source, clip, outpath):
    # Crop to vertical 9:16, keeping center. Optional source audio is preserved.
    vf="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    run_cmd(["ffmpeg","-y","-hide_banner","-loglevel","error","-ss",str(clip["start"]),"-i",str(source),"-t",str(clip["end"]-clip["start"]),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-b:a","128k","-movflags","+faststart",str(outpath)], timeout=60*30)

if run:
    if not url.strip():
        st.error("Cole primeiro um link.")
    elif not have("ffmpeg") or not have("ffprobe"):
        st.error("FFmpeg/FFprobe não encontrados. Instale FFmpeg e adicione à variável PATH.")
    elif not have("yt-dlp"):
        st.error("yt-dlp não encontrado. Rode pip install -r requirements.txt.")
    else:
        job = WORK_DIR / "latest"
        if job.exists(): shutil.rmtree(job)
        job.mkdir(parents=True)
        try:
            with st.status("Baixando e preparando a gravação...", expanded=True) as status:
                video = download_video(url.strip(), job)
                st.write(f"Arquivo recebido: {video.name} ({video.stat().st_size/1024/1024:.1f} MB)")
                duration = get_duration(video)
                if duration > 4*60*60:
                    raise RuntimeError("Este MVP limita o processamento a lives de até 4 horas. Use um VOD menor/recortado.")
                st.write(f"Duração: {fmt_time(duration)}")
                status.update(label="Analisando áudio e procurando momentos...", state="running")
                scores = audio_scores(video, duration)
                transcript=[]
                if use_transcription:
                    status.update(label="Transcrevendo fala (pode demorar)...", state="running")
                    transcript=transcribe(video, model_size)
                    (job/"transcript.json").write_text(json.dumps(transcript,ensure_ascii=False,indent=2),encoding="utf-8")
                clips=propose_clips(duration,clip_len,num_clips,scores,transcript)
                (job/"candidates.json").write_text(json.dumps(clips,ensure_ascii=False,indent=2),encoding="utf-8")
                status.update(label=f"Encontrados {len(clips)} candidatos", state="complete")
            st.subheader("Cortes candidatos")
            st.caption("A pontuação é heurística, não uma garantia de que o trecho seja interessante. Assista e ajuste antes de publicar.")
            for i,c in enumerate(clips,1):
                with st.container(border=True):
                    col1,col2,col3=st.columns([2,3,2])
                    col1.markdown(f"**Corte {i}**")
                    col1.write(f"{fmt_time(c['start'])} – {fmt_time(c['end'])}")
                    col2.write(c["reason"])
                    col2.progress(max(0,min(100,int(c["score"]*100)))/100)
                    col3.write(f"Pontuação: {c['score']:.2f}")
                    if c.get("text"): st.caption(c["text"])
                    if st.button(f"Exportar corte {i} em 9:16",key=f"export_{i}"):
                        out=job/f"livecut_{i:02d}_{int(c['start'])}.mp4"
                        with st.spinner("Renderizando vídeo..."):
                            export_clip(video,c,out)
                        st.success(f"Pronto: {out.name}")
                        st.video(str(out))
                        st.download_button("Baixar MP4",data=out.read_bytes(),file_name=out.name,mime="video/mp4",key=f"download_{i}")
            st.download_button("Baixar lista de candidatos (JSON)",data=json.dumps(clips,ensure_ascii=False,indent=2),file_name="cortes_candidatos.json",mime="application/json")
        except subprocess.TimeoutExpired:
            st.error("O processamento demorou mais do que o limite. Tente um VOD menor.")
        except Exception as e:
            st.error(f"Não consegui processar este link: {e}")
            st.caption("Alguns VODs podem estar indisponíveis, exigir autenticação ou bloquear download. O MVP não tenta contornar DRM, paywalls ou controles de acesso.")
