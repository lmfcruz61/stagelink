# StageHub - Guia de Testes Passo a Passo

Ambiente sugerido para este ciclo: Fly.io em `https://stagelink.fly.dev/`, Stripe em modo teste e Cloudflare Stream configurado com Live Input UID ou Video UID.

## 1. Preparacao

1. Abrir `https://stagelink.fly.dev/`.
2. Entrar no admin em `/admin/`.
3. Confirmar que existe pelo menos um utilizador admin ativo.
4. No admin, confirmar que o topo diz `Administracao do site`, mostra o nome do site e usa o logotipo configurado em `Aparencia do site`.
5. No admin, configurar `Aparencia do site`: nome, logotipo, imagem de fundo e overlay.
6. Confirmar variaveis do Fly.io: `SECRET_KEY`, `DATABASE_URL`, chaves Stripe, Redis/Upstash quando for usado chat multi-instancia.
7. Confirmar variaveis Cloudflare no Fly.io: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN` e `CLOUDFLARE_API_TOKEN`.
8. Confirmar que as variaveis Cloudflare da plataforma estao configuradas. O artista nao cria nem paga conta Cloudflare.

## 2. Teste como admin

1. Entrar como admin.
2. Abrir a homepage e confirmar header, logo, fundo e imagem de perfil.
3. Abrir `/admin/` e verificar Users, Artists, Organizations, Organization Members, EspetÃ¡culos, Subscriptions, Tips e Site Appearance.
4. Confirmar que o admin ve o nome/logo do site no cabecalho da administracao.
5. Criar ou rever uma equipa/empresa.
6. Criar ou rever artistas associados a essa equipa.
7. Abrir uma sala de espetÃ¡culo como admin. O admin deve entrar sem bilhete nem subscricao.
8. Confirmar que uploads de imagens aparecem no site publico.

## 3. Teste como artista individual

1. Criar conta nova como artista.
2. Entrar no dashboard.
3. Confirmar que nao aparecem botoes de equipa como `Nova equipa` ou `Novo artista gerido`.
4. Abrir o `Guia rapido`.
5. Editar pagina publica: nome artistico, frase, cidade, bio, foto principal, capa e links.
6. Adicionar varias fotos a galeria.
7. No perfil do artista, usar o botao `Criar Live Input` para criar automaticamente o Live Input na conta Cloudflare da StageHub.
8. Criar espetaculo com titulo, capa 16:9, tipo de conteudo, data futura e preco.
9. Para evento pago, usar Cloudflare Stream. Para evento gratuito, usar YouTube legado e nao usar gorjetas.
8. Para evento realmente em direto, escolher `Ao vivo`; para video preparado, escolher `Estreia` ou `Video gravado`; para conteudo passado ainda disponivel, escolher `Replay`.
9. Ativar o espetÃ¡culo.
10. Abrir a pagina publica do artista e confirmar:
   - capa visivel;
   - foto principal visivel;
   - bio e links;
   - galeria;
   - espetÃ¡culo agendado;
   - espetÃ¡culo ativo.
11. Entrar na sala como artista e confirmar countdown, player, badge do estado, marca do artista no video, chat, contador `a ver` e botoes de apoio.

## 4. Teste como manager / equipa

1. Criar conta de manager.
2. Entrar no dashboard.
3. Confirmar que aparecem `Nova equipa` e `Novo artista gerido`.
4. Criar `Nova equipa`.
5. Abrir a equipa e adicionar membros por username:
   - Dono;
   - Manager;
   - Editor;
   - Leitor.
6. Criar `Novo artista gerido` associado a equipa.
7. Selecionar o artista no dashboard.
8. Editar pagina publica desse artista.
9. Criar espetÃ¡culo para esse artista e escolher o tipo correto: `Ao vivo`, `Estreia`, `Video gravado` ou `Replay`.
10. Depois de um evento terminado, editar o espetÃ¡culo e mudar para `Replay` se o video continuar disponivel.
11. Entrar com outro membro da equipa e confirmar permissoes:
   - Dono/Manager/Editor conseguem gerir;
   - Leitor deve ficar limitado.
12. Confirmar que o manager consegue entrar na sala do espetÃ¡culo para operar/testar.

## 5. Teste como publico

1. Criar conta nova como publico.
2. Confirmar avatar circular por defeito no header/perfil.
3. Atualizar nome publico e foto do perfil.
4. Abrir a homepage e o `Guia rapido para o publico`.
5. Abrir pagina de um artista.
6. Marcar e remover artista favorito; confirmar estrela dourada na homepage.
7. Tentar entrar num espetÃ¡culo pago sem acesso. Deve aparecer bloqueio.
8. Comprar bilhete em modo teste ou criar acesso/subscricao de teste.
9. Entrar na sala.
10. Se o espetÃ¡culo ainda estiver no futuro, confirmar o estado `Agendado` e a contagem decrescente.
11. Confirmar que eventos aparecem com o estado correto: `Ao vivo`, `Estreia`, `Video gravado` ou `Replay disponivel`.
12. Confirmar que o nome do artista aparece discretamente no canto superior esquerdo do player.
13. Enviar mensagem no chat e confirmar que aparece imediatamente.
14. Enviar mensagem com emojis escritos manualmente, por exemplo `palmas`, `fogo` ou `coracao`.
15. Usar os botoes rapidos de emoji do chat: palmas, fogo, coracao, guitarra e musica.
16. Abrir outra janela/navegador com outro utilizador e confirmar chat em tempo real.
17. Confirmar que o contador `a ver` aumenta quando entra outro utilizador na sala e diminui quando fecha a janela.
18. Enviar gorjeta em modo teste.
19. Confirmar que a gorjeta aparece no dashboard do artista/manager.

## 6. Teste de pagamentos Stripe

1. Usar Stripe em modo teste.
2. Testar compra de bilhete one-time.
3. Testar subscricao mensal.
4. Testar gorjeta one-time.
5. Confirmar estados no dashboard e no admin.
6. Confirmar comportamento se o pagamento for cancelado.
7. Confirmar comportamento se o pagamento falhar.

## 7. Teste de Cloudflare Stream

1. No perfil do artista no StageHub, clicar em `Criar Live Input`.
2. Confirmar que o StageHub guardou Live Input UID, RTMPS URL e Stream Key.
3. Enviar ao artista apenas o RTMPS URL e a Stream Key para OBS.
4. No OBS, configurar `Servico: Personalizado`, `Servidor: RTMPS URL` e `Chave: Stream Key`.
5. Adicionar uma fonte no OBS, por exemplo webcam, captura de ecra ou ficheiro de video local.
6. Iniciar transmissao no OBS e confirmar no Cloudflare que o estado deixa de estar `Disconnected`.
7. Abrir a sala StageHub e confirmar que o player Cloudflare aparece.
8. Confirmar que o atraso existe no modo RTMPS/HLS e que este modo serve para MVP/concerto assistido, mas nao para interacao de latencia muito baixa.
9. Para video gravado, usar `Media > Stream > Videos`, copiar o `Video UID` e criar evento `Video gravado` ou `Replay`.
10. Testar em desktop e mobile.

Nota: eventos gratuitos usam YouTube legado e nao recebem gorjetas. Eventos pagos usam Cloudflare Stream e podem receber gorjetas.

## 8. Teste de sala ao vivo, chat e presenca

1. Criar um espetÃ¡culo marcado para daqui a 5 minutos e confirmar `Agendado` + countdown ao segundo.
2. Quando chegar a hora marcada, confirmar que o player aparece sem refresh manual.
3. Confirmar que um espetÃ¡culo ja iniciado abre diretamente com o player.
4. Criar/testar eventos dos tipos `Ao vivo`, `Estreia`, `Video gravado` e `Replay`.
5. Confirmar que video gravado e replay nunca aparecem como `Ao vivo`.
6. Confirmar que o badge no player mostra estado + nome do artista.
7. Entrar na mesma sala com dois utilizadores diferentes.
8. Confirmar que ambos veem o player e o chat.
9. Confirmar que o contador `a ver` aparece junto ao titulo do espetÃ¡culo e no cabecalho do chat.
10. Confirmar que o contador mostra pelo menos `2 a ver` quando existem dois browsers ligados.
11. Enviar texto normal, texto com acentos e texto com emojis.
12. Confirmar que emojis aparecem corretamente para todos os utilizadores ligados.
13. Fechar uma das janelas e confirmar que a contagem reduz.
14. Recarregar a pagina e confirmar que o WebSocket volta a ligar ao chat.

Nota: nesta fase piloto, o contador mede ligacoes WebSocket ativas na sala. Em escala com varias maquinas Fly.io, deve passar para presenca partilhada via Redis/Upstash.

## 9. Teste mobile e navegadores

1. Testar Chrome desktop.
2. Testar Edge desktop.
3. Testar mobile estreito.
4. Confirmar que header, avatar, botoes, cards, player, chat e formularios nao se sobrepoem.
5. Confirmar uploads e imagens em paginas publicas.

## 10. Criterios para falar com artista piloto

Avancar para um artista piloto quando:

1. Registo de artista, manager e publico nao tiver erros 500.
2. Pagamentos Stripe em modo teste estiverem completos.
3. Chat funcionar entre pelo menos dois utilizadores.
4. Emojis do chat aparecerem corretamente.
5. Contador `a ver` atualizar ao abrir/fechar uma segunda janela.
6. Admin conseguir entrar em qualquer espetÃ¡culo.
7. Pagina publica do artista estiver visualmente apresentavel.
8. Existir um guiao simples para o artista preparar o Cloudflare Stream/OBS.
9. Estados dos eventos aparecerem corretamente: agendado, ao vivo, estreia, video gravado e replay.

## 11. Resultado esperado

No fim deste teste, deves conseguir provar o ciclo completo:

Empresa/manager cria artista, artista tem pagina publica, espetÃ¡culo com tipo correto e acesso pago; publico entra, ve countdown/player com marca do artista, conversa no chat, usa emojis, ve a contagem de espectadores e envia gorjeta; admin consegue supervisionar tudo.

