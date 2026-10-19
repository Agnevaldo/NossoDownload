# Nosso Download — Instagram

Site pessoal sem anúncios para baixar vídeos públicos do Instagram, usando yt-dlp.

## Instalar gratuitamente no Render (pelo celular)

1. Crie uma conta gratuita em https://github.com e faça um repositório **Public** chamado `nosso-download`.
2. No repositório, toque em **Add file > Upload files** e envie os arquivos `app.py`, `requirements.txt` e `render.yaml` deste pacote. Salve em **Commit changes**.
3. Crie uma conta gratuita em https://render.com (pode entrar com o GitHub).
4. Vá a https://dashboard.render.com/select-repo?type=blueprint ou escolha **New > Blueprint**, selecione o repositório `nosso-download` e autorize a instalação.
5. Confirme a configuração. O arquivo `render.yaml` determina o plano `free`; **não selecione um plano pago**.
6. Depois do deploy, a Render mostra um endereço fixo como `https://nosso-download-instagram-xxxx.onrender.com`. Salve nos favoritos do navegador.

**Atenção:** o plano Render Free para após 15 minutos sem uso e desperta ao abrir (pode levar cerca de 1 minuto). Possui limites mensais de processamento/banda, e não garante uptime de 24 horas. Os vídeos devem ser públicos; não forneça senha ou cookies. Alguns downloads podem falhar por bloqueio de IP do Instagram. Vídeos armazenados temporariamente para entregar ao navegador; não há armazenamento permanente.

## Arquivos
- `app.py`: site e servidor para downloads com limite de 100 MB.
- `requirements.txt`: pacotes Python.
- `render.yaml`: configuração automática da hospedagem gratuita.

## Segurança e uso
Use apenas vídeos próprios ou autorizados. Não dá acesso a perfis privados, não contorna autenticação, não pede senha. O site público inclui limite básico de 15 solicitações por IP a cada hora para reduzir abuso.
