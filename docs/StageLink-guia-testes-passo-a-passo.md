# StageLink - Guia de Testes Passo a Passo

Ambiente sugerido para este ciclo: Fly.io em `https://stagelink.fly.dev/`, Stripe em modo teste e YouTube com video publico ou nao listado com incorporacao ativa.

## 1. Preparacao

1. Abrir `https://stagelink.fly.dev/`.
2. Entrar no admin em `/admin/`.
3. Confirmar que existe pelo menos um utilizador admin ativo.
4. No admin, confirmar que o topo diz `Administracao do site`, mostra o nome do site e usa o logotipo configurado em `Aparencia do site`.
5. No admin, configurar `Aparencia do site`: nome, logotipo, imagem de fundo e overlay.
6. Confirmar variaveis do Fly.io: `SECRET_KEY`, `DATABASE_URL`, chaves Stripe, Redis/Upstash quando for usado chat multi-instancia.
7. Confirmar que o YouTube usado no teste permite embed.

## 2. Teste como admin

1. Entrar como admin.
2. Abrir a homepage e confirmar header, logo, fundo e imagem de perfil.
3. Abrir `/admin/` e verificar Users, Artists, Organizations, Organization Members, Streams, Subscriptions, Tips e Site Appearance.
4. Confirmar que o admin ve o nome/logo do site no cabecalho da administracao.
5. Criar ou rever uma equipa/empresa.
6. Criar ou rever artistas associados a essa equipa.
7. Abrir uma sala de stream como admin. O admin deve entrar sem bilhete nem subscricao.
8. Confirmar que uploads de imagens aparecem no site publico.

## 3. Teste como artista individual

1. Criar conta nova como musico.
2. Entrar no dashboard.
3. Confirmar que nao aparecem botoes de equipa como `Nova equipa` ou `Novo artista gerido`.
4. Abrir o `Guia rapido`.
5. Editar pagina publica: nome artistico, frase, cidade, bio, foto principal, capa e links.
6. Adicionar varias fotos a galeria.
7. Criar stream com titulo, capa 16:9, data futura, preco e ID/link YouTube.
8. Ativar o stream.
9. Abrir a pagina publica do artista e confirmar:
   - capa visivel;
   - foto principal visivel;
   - bio e links;
   - galeria;
   - concerto agendado;
   - stream ativo.
10. Entrar na sala como artista e confirmar player, chat, contador `a ver` e botoes de apoio.

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
9. Criar stream para esse artista.
10. Entrar com outro membro da equipa e confirmar permissoes:
   - Dono/Manager/Editor conseguem gerir;
   - Leitor deve ficar limitado.
11. Confirmar que o manager consegue entrar na sala do stream para operar/testar.

## 5. Teste como publico

1. Criar conta nova como publico.
2. Confirmar avatar circular por defeito no header/perfil.
3. Atualizar nome publico e foto do perfil.
4. Abrir a homepage e o `Guia rapido para o publico`.
5. Abrir pagina de um artista.
6. Marcar e remover artista favorito; confirmar estrela dourada na homepage.
7. Tentar entrar num stream pago sem acesso. Deve aparecer bloqueio.
8. Comprar bilhete em modo teste ou criar acesso/subscricao de teste.
9. Entrar na sala.
10. Enviar mensagem no chat e confirmar que aparece imediatamente.
11. Enviar mensagem com emojis escritos manualmente, por exemplo `👏🔥❤️`.
12. Usar os botoes rapidos de emoji do chat: palmas, fogo, coracao, guitarra e musica.
13. Abrir outra janela/navegador com outro utilizador e confirmar chat em tempo real.
14. Confirmar que o contador `a ver` aumenta quando entra outro utilizador na sala e diminui quando fecha a janela.
15. Enviar gorjeta em modo teste.
16. Confirmar que a gorjeta aparece no dashboard do artista/manager.

## 6. Teste de pagamentos Stripe

1. Usar Stripe em modo teste.
2. Testar compra de bilhete one-time.
3. Testar subscricao mensal.
4. Testar gorjeta one-time.
5. Confirmar estados no dashboard e no admin.
6. Confirmar comportamento se o pagamento for cancelado.
7. Confirmar comportamento se o pagamento falhar.

## 7. Teste de YouTube

1. Usar video publico ou nao listado.
2. Confirmar que a incorporacao esta permitida no YouTube Studio.
3. Testar video valido.
4. Testar video privado ou bloqueado para confirmar mensagem/limite esperado.
5. Testar em desktop e mobile.

## 8. Teste de sala ao vivo, chat e presenca

1. Entrar na mesma sala com dois utilizadores diferentes.
2. Confirmar que ambos veem o player e o chat.
3. Confirmar que o contador `a ver` aparece junto ao titulo do concerto e no cabecalho do chat.
4. Confirmar que o contador mostra pelo menos `2 a ver` quando existem dois browsers ligados.
5. Enviar texto normal, texto com acentos e texto com emojis.
6. Confirmar que emojis aparecem corretamente para todos os utilizadores ligados.
7. Fechar uma das janelas e confirmar que a contagem reduz.
8. Recarregar a pagina e confirmar que o WebSocket volta a ligar ao chat.

Nota: nesta fase piloto, o contador mede ligacoes WebSocket ativas na sala. Em escala com varias maquinas Fly.io, deve passar para presenca partilhada via Redis/Upstash.

## 9. Teste mobile e navegadores

1. Testar Chrome desktop.
2. Testar Edge desktop.
3. Testar mobile estreito.
4. Confirmar que header, avatar, botoes, cards, player, chat e formularios nao se sobrepoem.
5. Confirmar uploads e imagens em paginas publicas.

## 10. Criterios para falar com artista piloto

Avancar para um artista piloto quando:

1. Registo de musico, manager e publico nao tiver erros 500.
2. Pagamentos Stripe em modo teste estiverem completos.
3. Chat funcionar entre pelo menos dois utilizadores.
4. Emojis do chat aparecerem corretamente.
5. Contador `a ver` atualizar ao abrir/fechar uma segunda janela.
6. Admin conseguir entrar em qualquer stream.
7. Pagina publica do artista estiver visualmente apresentavel.
8. Existir um guiao simples para o artista preparar o YouTube.

## 11. Resultado esperado

No fim deste teste, deves conseguir provar o ciclo completo:

Empresa/manager cria artista, artista tem pagina publica, stream e acesso pago; publico entra, conversa no chat, usa emojis, ve a contagem de espectadores e envia gorjeta; admin consegue supervisionar tudo.
