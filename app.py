"""Nosso Download: interface leve para vídeos públicos do Instagram.
Hospedagem: Railway/Render (Flask + Gunicorn + yt-dlp + FFmpeg).
"""

from collections import defaultdict, deque
from pathlib import Path
from threading import BoundedSemaphore, Lock
from urllib.parse import urlsplit
import os
import mimetypes
import re
import shutil
import tempfile
import time
import uuid

from flask import Flask, jsonify, render_template_string, request, send_file
from werkzeug.middleware.proxy_fix import ProxyFix
import yt_dlp

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config["MAX_CONTENT_LENGTH"] = 8192

PASTA = Path(tempfile.gettempdir()) / "nosso_download_web"
PASTA.mkdir(exist_ok=True)
LIMITE_BYTES = 100 * 1024 * 1024
TEMPO_ARQUIVO = 15 * 60  # Disponível para baixar por 15 minutos.
LIMITE_HORA = 15         # Limite simples por IP para evitar abuso.

trabalhando = BoundedSemaphore(1)
trava = Lock()
arquivos = {}  # token -> (pasta, arquivo, nome, horario)
acessos = defaultdict(deque)

PAGINA = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0d1020">
<meta name="robots" content="noindex, nofollow">
<title>Nosso Download — Instagram</title>
<style>
:root { color-scheme: dark; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }
* { box-sizing: border-box; }
body { margin:0; padding: max(36px, env(safe-area-inset-top)) 18px 35px; background: radial-gradient(circle at 50% -10%, #27255b 0%, #111426 50%, #0c1020 100%); color:#f5f6ff; min-height:100vh; }
main { max-width:540px; margin: 0 auto; }
.logo { display:inline-flex; align-items:center; justify-content:center; width:64px; height:64px; background: #5348ef; border-radius:18px; font-size:32px; margin-bottom:15px; box-shadow: 0 14px 45px #302d9e55; }
h1 { font-size:clamp(2rem, 8vw, 2.7rem); letter-spacing:-1.1px; margin:0 0 8px; }
p.sub { color:#aeb6ce; line-height:1.55; font-size:16px; margin:0 0 25px; }
.tag { color:#9ff4c6; border:1px solid #426956; background:#1c392f; padding:7px 12px; border-radius:20px; display:inline-block; font-weight:700; font-size:13px; margin:0 0 13px; }
.box { border:1px solid #383e59; padding:22px 18px; border-radius:22px; background:#1b2134; box-shadow:0 16px 45px #04081666; }
label { display:block; font-size:15px; font-weight:700; margin-bottom:10px; }
input { display:block; width:100%; border-radius:12px; border:1px solid #485471; padding:16px; background:#303a52; color:#fff; font-size:16px; min-height:56px; outline:none; }
input:focus { border-color:#928aff; box-shadow:0 0 0 3px #625af355; }
input::placeholder { color:#a5adc3; }
button,.link { width:100%; border:0; border-radius:12px; background:#564cf1; color:white; display:flex; align-items:center; justify-content:center; text-align:center; font-size:17px; font-weight:800; padding:17px 12px; margin-top:18px; cursor:pointer; min-height:57px; text-decoration:none; }
button:active,.link:active { background:#4239c4; }
button:disabled { cursor:wait; opacity:.63; }
.msg { color:#b9c0d3; line-height:1.6; font-size:15px; margin-top:20px; min-height:24px; overflow-wrap:anywhere; }
.msg.ok { color:#9ff4c6; }
.msg.erro { color:#ffb6bb; }
#resultado { display:none; padding-top:4px; }
.link { background:#238c5c; margin-top:12px; }
footer { text-align:center; margin-top:26px; color:#a8b1c8; font-size:13px; line-height:1.7; }
.spin { width:18px; height:18px; border:2px solid #ffffff6b; border-top-color:#fff; border-radius:100%; display:inline-block; animation:girar .7s linear infinite; margin-right:11px; }
@keyframes girar { to { transform: rotate(360deg) } }
</style>
</head>
<body>
<main>
  <div class="logo" aria-hidden="true">📥</div>
  <div class="tag">✓ Sem anúncios</div>
  <h1>Nosso Download</h1>
  <p class="sub">Baixe Reels e vídeos públicos do Instagram direto no celular ou no PC.</p>
  <section class="box">
    <form id="formulario">
      <label for="url">Link do Instagram</label>
      <input id="url" name="url" type="url" required maxlength="2048" inputmode="url" autocomplete="off" spellcheck="false" placeholder="https://www.instagram.com/reel/...">
      <button type="submit" id="botao">⬇ Baixar vídeo</button>
    </form>
    <div id="mensagem" class="msg" role="status" aria-live="polite">Cole o link acima e toque em Baixar vídeo.</div>
    <div id="resultado"><a id="arquivo" class="link" href="#" rel="nofollow" download>📥 Salvar vídeo no aparelho</a></div>
  </section>
  <footer>Não é necessário fazer login. Não informe sua senha.<br>Use apenas vídeos seus ou com autorização.<br>Limite por vídeo: 100 MB.</footer>
</main>
<script>
const form = document.getElementById('formulario');
const input = document.getElementById('url');
const botao = document.getElementById('botao');
const mensagem = document.getElementById('mensagem');
const resultado = document.getElementById('resultado');
const arquivo = document.getElementById('arquivo');
function aviso(texto, estado='') { mensagem.textContent=texto; mensagem.className='msg '+estado; }
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  resultado.style.display='none';
  botao.disabled=true;
  botao.innerHTML='<span class="spin"></span>Preparando o vídeo...';
  aviso('Aguarde um pouco. Estamos procurando o vídeo no Instagram.');
  try {
    const resposta=await fetch('/api/baixar', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:input.value.trim()})});
    const data=await resposta.json();
    if (!resposta.ok || !data.ok) { aviso(data.erro || 'Não foi possível baixar este vídeo.','erro'); return; }
    arquivo.href=data.link;
    arquivo.setAttribute('download',data.nome);
    aviso('✅ Vídeo pronto! Toque no botão verde para salvar.','ok');
    resultado.style.display='block';
  } catch (_) { aviso('❌ Não foi possível conectar. Aguarde e tente novamente.','erro'); }
  finally { botao.disabled=false; botao.textContent='⬇ Baixar vídeo'; }
});
</script>
</body>
</html>"""


def limpar_antigos():
    agora = time.time()
    with trava:
        velhos = [token for token, (_, _, _, t) in arquivos.items() if agora - t > TEMPO_ARQUIVO]
        pastas = [arquivos.pop(token)[0] for token in velhos]
        for ip in list(acessos):
            while acessos[ip] and agora - acessos[ip][0] >= 3600:
                acessos[ip].popleft()
            if not acessos[ip]:
                del acessos[ip]
    for pasta in pastas:
        shutil.rmtree(pasta, ignore_errors=True)


def url_valida(link):
    if not isinstance(link, str) or len(link) > 2048:
        return False
    try:
        parsed = urlsplit(link.strip())
        if parsed.scheme not in ("https", "http"):
            return False
        if parsed.username or parsed.password or parsed.port:
            return False
        if (parsed.hostname or "").lower() not in {
            "instagram.com", "www.instagram.com", "m.instagram.com",
            "instagr.am", "www.instagr.am",
        }:
            return False
        if not any(parsed.path.startswith(p) for p in ("/reel/", "/reels/", "/p/", "/tv/")):
            return False
        return True
    except ValueError:
        return False


def resposta_erro(mensagem, status=400):
    return jsonify(ok=False, erro=mensagem), status


@app.get("/")
def inicio():
    return render_template_string(PAGINA)


@app.get('/robots.txt')
def robots():
    return 'User-agent: *\nDisallow: /\n', 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.get('/health')
def health():
    return jsonify(ok=True)


@app.post('/api/baixar')
def baixar():
    limpar_antigos()
    corpo = request.get_json(silent=True)
    link = (corpo or {}).get('url', '') if isinstance(corpo, dict) else ''
    if not url_valida(link):
        return resposta_erro('Cole um link de vídeo ou Reel público do Instagram.')
    ip = request.remote_addr or 'desconhecido'
    agora = time.time()
    with trava:
        fila = acessos[ip]
        while fila and agora - fila[0] >= 3600:
            fila.popleft()
        if len(fila) >= LIMITE_HORA:
            return resposta_erro('Limite de downloads por hora atingido. Tente novamente mais tarde.', 429)

    if not trabalhando.acquire(blocking=False):
        return resposta_erro('Estamos preparando outro vídeo. Aguarde alguns segundos e tente novamente.', 429)

    pasta = PASTA / uuid.uuid4().hex
    pasta.mkdir(parents=True)
    try:
        with trava:
            acessos[ip].append(time.time())

        def progresso(info):
            if info.get('status') == 'downloading':
                tamanho = info.get('downloaded_bytes') or 0
                if tamanho > LIMITE_BYTES:
                    raise yt_dlp.utils.DownloadError('Arquivo excede 100 MB')

        opcoes = {
            'outtmpl': str(pasta / '%(id)s.%(ext)s'),
            # Primeiro tenta vídeo e áudio separados, juntando com FFmpeg.
            # Se não existirem faixas separadas, usa MP4 já com áudio.
            'format': 'bv[ext=mp4]+ba[ext=m4a]/bv+ba/b[ext=mp4]/b',
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 20,
            'retries': 2,
            'fragment_retries': 2,
            'max_filesize': LIMITE_BYTES,
            'progress_hooks': [progresso],
        }
        with yt_dlp.YoutubeDL(opcoes) as downloader:
            info = downloader.extract_info(link, download=True)

        # Seleciona somente vídeo finalizado, nunca áudio avulso ou temporários.
        candidatos = [p for p in pasta.iterdir()
                      if p.is_file() and p.suffix.lower() in ('.mp4', '.mkv', '.webm', '.mov')]
        if not candidatos:
            return resposta_erro('O Instagram não disponibilizou um arquivo de vídeo para este link.', 422)
        arquivo = max(candidatos, key=lambda p: p.stat().st_size)
        if arquivo.stat().st_size > LIMITE_BYTES:
            return resposta_erro('O vídeo passa de 100 MB, limite desta versão.', 413)
        identificador = re.sub(r'[^0-9A-Za-z_-]', '', str((info or {}).get('id', 'video')))[:50] or 'video'
        nome = f'NossoDownload_{identificador}{arquivo.suffix.lower()}'
        token = uuid.uuid4().hex
        with trava:
            arquivos[token] = (pasta, arquivo, nome, time.time())
        return jsonify(ok=True, link=f'/download/{token}', nome=nome)
    except Exception:
        app.logger.exception('Falha no processamento do video')
        return resposta_erro('Não conseguimos baixar este vídeo. O Instagram pode ter bloqueado o servidor ou exigido login.', 422)
    finally:
        with trava:
            mantida = any(info[0] == pasta for info in arquivos.values())
        if not mantida:
            shutil.rmtree(pasta, ignore_errors=True)
        trabalhando.release()


@app.get('/download/<token>')
def entregar(token):
    limpar_antigos()
    if not re.fullmatch(r'[0-9a-f]{32}', token):
        return 'Link inválido.', 404
    with trava:
        resultado = arquivos.pop(token, None)
    if not resultado:
        return 'Link expirado ou já utilizado. Cole o link do Instagram novamente.', 404
    pasta, arquivo, nome, _ = resultado
    if not arquivo.is_file():
        return 'Arquivo indisponível. Tente novamente.', 404
    try:
        resposta = send_file(arquivo, as_attachment=True, download_name=nome, mimetype=mimetypes.guess_type(nome)[0] or 'application/octet-stream', conditional=False)
        resposta.call_on_close(lambda: shutil.rmtree(pasta, ignore_errors=True))
        return resposta
    except OSError:
        shutil.rmtree(pasta, ignore_errors=True)
        return 'Arquivo indisponível. Tente novamente.', 404


@app.after_request
def cabecalhos(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store'
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '7860')))
