# StageHub - Testes feitos

Data: 2026-06-25

Este ficheiro resume os testes ja executados por Codex e que justificam os checks marcados no ficheiro `StageHub-checklist-testes-site.md`.

## Resultado geral

- `python manage.py check`: OK
- `python manage.py test`: 95 testes OK
- Deploy Fly feito na versao 90
- Producao validada internamente na maquina Fly com resposta HTTP 200 para `stagehub.pt`
- Logs Fly sem erro 500 recente depois do deploy

## Areas confirmadas por testes automaticos

### Paginas legais e rodape

- Politica de Privacidade abre.
- Politica de Cookies abre.
- Termos e Condicoes abre.
- Footer contem links para paginas legais, contacto e gestao de cookies.

### Contactos

- `/contacto` abre.
- Formulario grava mensagem na base de dados.
- Formulario envia email com assunto categorizado.
- Prefixo tecnico validado: `[STAGEHUB - TECNICO]`.
- Protecao anti-spam por honeypot validada.
- Admin consegue listar e tratar contactos.

### Conta e registo

- Link de recuperacao de password aparece no login.
- Pagina de recuperacao de password abre.
- Registo rejeita email ja usado noutra conta, sem alterar contas existentes.
- Validacao de email duplicado nao distingue maiusculas/minusculas.
- Novos emails de registo sao guardados em minusculas.

### Dashboard e Stripe

- Dashboard mostra orientacao antes de ligar Stripe.
- Dashboard mostra resumo financeiro quando Stripe esta ativo.
- Dashboard exclui pagamentos Stripe em modo teste do resumo real.
- Conta Connect pronta abre painel Stripe Express.
- Webhook `account.updated` atualiza o estado Stripe do artista.
- Webhook ignora contas Stripe desconhecidas sem erro.
- Compra de bilhete usa destination charge com comissao StageHub.
- Compra de galeria usa destination charge com comissao StageHub.
- Artista sem Stripe Connect completo fica bloqueado para vendas pagas.

### Comissoes

- Comissao padrao de 20% calcula corretamente.
- Comissao reduzida de 10% calcula corretamente.
- Comissao de 0% calcula corretamente.
- Comissao valida apenas valores entre 0 e 100.
- Pagamentos guardam percentagem e valores no momento da compra.

### Modos de monetizacao

- Somente subscricao bloqueia compra avulsa.
- Subscricao e material pago exclusivo exige subscricao para comprar.
- Somente material pago bloqueia novas subscricoes.
- Artista com subscricoes ativas nao pode mudar diretamente para somente material pago.

### Upload de fotos simples do artista

- Pagina `Editar pagina` abre para o artista.
- Upload de foto simples cria `ArtistPhoto`.
- Limite de 10 fotos por envio validado.
- Limite de 5 MB por foto validado.
- Limite de 30 MB total apresentado na pagina.

### Galerias pagas

- Preco abaixo de 2 EUR e rejeitado.
- Upload de mais de 10 fotos e rejeitado.
- Foto privada acima de 3 MB e rejeitada.
- Envio total acima de 30 MB e rejeitado.
- Galeria aprovada aparece na homepage.
- Galeria pendente aparece como notificacao no admin.
- Admin aprova galeria e ela fica ativa.
- Galeria pendente nao aparece ao publico.
- Capa publica aparece antes da compra.
- Fotos privadas nao aparecem antes da compra.
- Comprador pago consegue ver fotos privadas.
- Galeria paga removida fica arquivada, nao apagada.
- Foto de galeria paga nao pode ser apagada isoladamente.
- Conteudo sensivel exige confirmacao de idade antes da visualizacao publica.

### Videos

- Formulario de video aceita edicao simples de titulo.
- Video gravado Cloudflare permite upload direto sem UID inicial.
- Videos com mais de 1 hora sao recusados na criacao e edicao.
- Preco minimo de 2 EUR para eventos e validado.
- Upload direto Cloudflare cria URL e UID.
- Upload direto Cloudflare limita duracao maxima a 1 hora.
- Embed Cloudflare normaliza varios formatos de URL/ID.
- Sala de video gravado pendente mostra mensagem clara em vez de parecer erro do player.
- Artista consegue preparar novo link de upload para video gravado pendente.
- Upload direto Cloudflare usa o endpoint Tus da Cloudflare sem metadata e sem retoma local, evitando erros 400 no inicio do upload.

### Lives e OBS

- TC-LIVE-001: formulario de live StageHub aceita criacao sem ID manual de video.
- TC-LIVE-002: criacao de live prepara/reutiliza canal ao vivo do artista e guarda dados OBS.
- TC-LIVE-003: pagina de edicao de live mostra configuracao OBS recomendada.
- TC-LIVE-004: recomendacoes OBS aparecem com 1280x720, 30 FPS, bitrate 4000-6000 kbps, keyframe 2 segundos e x264 veryfast.
- TC-LIVE-005: pagina publica do artista mostra badge vermelho `Ao vivo` quando a live esta ativa.
- TC-LIVE-006: sala da live mantem contagem decrescente antes da hora marcada.
- TC-LIVE-007: ao terminar a contagem, a sala troca o estado visual para `Ao vivo`.
- TC-LIVE-008: dashboard, homepage e pagina publica mantem botoes separados para `Novo video` e `Nova live`.
- TC-LIVE-009: live antiga/sem dados OBS permite preparar dados diretamente na edicao.
- TC-LIVE-010: edicao de live mostra data/hora em formato local e botao claro `Ativar live`.
- TC-LIVE-011: lives novas e antigas nao podem ficar com preco abaixo de 2 EUR.
- TC-LIVE-012: edicao de live mostra o canal StageHub ao vivo ligado ao artista.
- TC-LIVE-013: nova live abre com preco inicial de bilhete a 2 EUR.
- TC-LIVE-014: migracao corrige eventos existentes com preco inferior a 2 EUR para 2 EUR.
- TC-LIVE-015: live futura paga aparece na pagina publica do artista mesmo estando inativa.
- TC-LIVE-016: live abaixo de 2 EUR nao aparece ao publico.
- TC-LIVE-017: falha ao preparar dados OBS/Cloudflare nao apaga nem impede a gravacao da live.
- TC-LIVE-018: token Cloudflare Stream em producao permite criar canal live/OBS.
- TC-LIVE-019: dados OBS reais foram gerados para o artista SIULC.
- TC-LIVE-020: teste real OBS enviou imagem para a sala StageHub, com delay aproximado de 10 segundos.
- TC-LIVE-021: teste real OBS enviou som para a sala StageHub.

### Admin e media Cloudflare

- Area admin de media Cloudflare lista video referenciado.
- Eliminacao admin de video chama API Cloudflare.
- Eliminacao admin regista log.

## Verificacoes feitas em producao

- Fly app `stagelink` em versao 90.
- Maquina principal em estado `started`.
- App responde internamente com HTTP 200 usando `Host: stagehub.pt`.
- Banda HappyHour ficou sem conta Stripe de teste antiga e criou nova conta live:
  - `acct_1Tlqq9HQjuzzkT0l`
  - ainda pendente na Stripe por falta de dados do representante, IBAN e termos.
- Ana Derrica foi verificada na Stripe live:
  - conta existe;
  - ainda nao tem `charges_enabled` nem `payouts_enabled`;
  - Stripe pede dados pessoais/contacto/morada.
- SIULC foi verificado como ativo na Stripe live.
- Cloudflare Stream foi corrigido em producao:
  - `CLOUDFLARE_API_TOKEN` atualizado;
  - canal live/OBS criado para SIULC;
  - RTMPS e chave de transmissao ficaram disponiveis no artista.
- Live real testada com OBS:
  - imagem chegou a sala;
  - som chegou a sala;
  - delay observado perto de 10 segundos;
- Emails duplicados existentes foram apenas consultados, sem apagar nem alterar contas:
  - `SIULC`
  - `Stage_Team`
  - `Luis`
  - `Happy`

## Ainda precisa de teste manual

- Registo completo de novo utilizador real.
- Recuperacao de password fim a fim com email real.
- Confirmacao visual do logo, imagem de fundo e layout mobile.
- Upload de foto principal e capa por artista real.
- Fotos simples aparecerem visualmente na pagina publica.
- Criacao completa de galeria paga por artista real.
- Checkout Stripe real de bilhete/galeria/subscricao/gorjeta.
- Retorno do pagamento real ao site.
- Validacao visual de acesso ao video comprado.
- Fluxo Stripe Express completo por artista real.
- Confirmar no painel Stripe live que o webhook inclui `account.updated`.
