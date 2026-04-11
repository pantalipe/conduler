# conduler

Agendador de publicacao de videos curtos para Instagram Reels, YouTube Shorts e TikTok.

Projeto separado do [Rotman](../rotman) — o Rotman gera o video, o conduler agenda e publica.

## Requisitos

- Python 3.8+
- Sem dependencias externas (stdlib apenas)

## Como usar

### 1. Configurar credenciais

Edite `config.py` ou defina variaveis de ambiente:

```
INSTAGRAM_APP_ID        INSTAGRAM_APP_SECRET
YOUTUBE_CLIENT_ID       YOUTUBE_CLIENT_SECRET
TIKTOK_CLIENT_KEY       TIKTOK_CLIENT_SECRET
```

### 2. Iniciar o servidor

```bash
python main.py
```

Acesse: http://127.0.0.1:7071

### 3. Autenticar as plataformas

Na aba **Autenticacao**, clique em **Conectar** para cada plataforma.
O fluxo OAuth abre no browser e salva o token em `auth/tokens.json` (gitignored).

### 4. Agendar um video

- Coloque o video na pasta monitorada (padrao: `watch_input/`, configuravel via `WATCH_FOLDER`)
- Na aba **Agendar**, selecione o arquivo, preencha titulo/descricao e escolha o horario
- O Scheduler verifica a fila a cada 15 segundos e publica quando o horario chegar

## Estrutura

```
conduler/
├── main.py              # servidor HTTP + entrypoint
├── watcher.py           # monitora a pasta de videos
├── scheduler.py         # fila de jobs + engine de agendamento
├── publisher_router.py  # despacha jobs para cada plataforma
├── config.py            # configuracoes centrais
├── publishers/
│   ├── instagram.py     # Graph API v21
│   ├── youtube.py       # Data API v3
│   └── tiktok.py        # Content Posting API v2
├── auth/
│   └── oauth_flow.py    # fluxo OAuth via urllib
├── ui/
│   └── index.html       # interface web
├── watch_input/         # pasta monitorada (gitignored)
└── jobs.example.json    # exemplo de jobs.json
```

## Portas

| Servico                     | Porta |
|-----------------------------|-------|
| conduler (UI/API)            | 7071  |
| Rotman                      | 7070  |
| OAuth callback (temporario) | 7072  |

## Observacoes sobre as APIs

**Instagram** exige que o video esteja disponivel em uma URL publica no momento da publicacao
(campo `video_url` no job). Para testes, use ngrok ou servico de hospedagem temporaria.

**YouTube** faz o upload diretamente do arquivo local — sem necessidade de URL publica.

**TikTok** exige aprovacao do app no portal de desenvolvedores. O fluxo esta implementado
mas so funciona com um app aprovado.

## Roadmap

- [ ] Suporte a upload direto para Instagram (sem URL publica)
- [ ] Refresh automatico de tokens expirados
- [ ] Notificacao por webhook apos publicacao
- [ ] Integracao direta com o Rotman via pasta compartilhada
