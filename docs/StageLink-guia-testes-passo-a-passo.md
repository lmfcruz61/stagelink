# StageLink - Guia de Testes Passo a Passo

Ambiente sugerido para este ciclo: Fly.io em `https://stagelink.fly.dev/`, Stripe em modo teste e YouTube com video publico ou nao listado com incorporacao ativa.

## 1. Preparacao

1. Abrir `https://stagelink.fly.dev/`.
2. Entrar no admin em `/admin/`.
3. Confirmar que existe pelo menos um utilizador admin ativo.
4. No admin, configurar `Aparencia do site`: nome, logotipo, imagem de fundo e overlay.
5. Confirmar variaveis do Fly.io: `SECRET_KEY`, `DATABASE_URL`, chaves Stripe, Redis/Upstash quando for usado chat multi-instancia.
6. Confirmar que o YouTube usado no teste permite embed.

## 2. Teste como admin

1. Entrar como admin.
2. Abrir a homepage e confirmar header, logo, idioma e fundo.
3. Abrir `/admin/` e verificar Users, Artists, Organizations, Organization Members, Streams, Subscriptions, Tips e Site Appearance.
4. Criar ou rever uma equipa/empresa.
5. Criar ou rever artistas associados a essa equipa.
6. Abrir uma sala de stream como admin. O admin deve entrar sem bilhete nem subscricao.
7. Confirmar que uploads de imagens aparecem no site publico.

## 3. Teste como artista individual

1. Criar conta nova como musico.
2. Entrar no dashboard.
3. Abrir o `Guia rapido`.
4. Editar pagina publica: nome artistico, frase, cidade, bio, foto principal, capa e links.
5. Adicionar varias fotos a galeria.
6. Criar stream com titulo, capa 16:9, data futura, preco e ID/link YouTube.
7. Ativar o stream.
8. Abrir a pagina publica do artista e confirmar:
   - capa visivel;
   - foto principal visivel;
   - bio e links;
   - galeria;
   - concerto agendado;
   - stream ativo.
9. Entrar na sala como artista e confirmar player, chat e botoes.

## 4. Teste como manager / equipa

1. Criar conta de manager.
2. Entrar no dashboard.
3. Criar `Nova equipa`.
4. Abrir a equipa e adicionar membros por username:
   - Dono;
   - Manager;
   - Editor;
   - Leitor.
5. Criar `Novo artista gerido` associado a equipa.
6. Selecionar o artista no dashboard.
7. Editar pagina publica desse artista.
8. Criar stream para esse artista.
9. Entrar com outro membro da equipa e confirmar permissoes:
   - Dono/Manager/Editor conseguem gerir;
   - Leitor deve ficar limitado.
10. Confirmar que o manager consegue entrar na sala do stream para operar/testar.

## 5. Teste como fa

1. Criar conta nova como fa.
2. Confirmar avatar circular por defeito no header/perfil.
3. Atualizar nome publico e foto do perfil.
4. Abrir a homepage e o `Guia rapido para fas`.
5. Abrir pagina de um artista.
6. Tentar entrar num stream pago sem acesso. Deve aparecer bloqueio.
7. Comprar bilhete em modo teste ou criar acesso/subscricao de teste.
8. Entrar na sala.
9. Enviar mensagem no chat e confirmar que aparece imediatamente.
10. Abrir outra janela/navegador com outro utilizador e confirmar chat em tempo real.
11. Enviar gorjeta em modo teste.
12. Confirmar que a gorjeta aparece no dashboard do artista/manager.

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

## 8. Teste de idiomas

1. Alternar PT, EN, ES, FR e DE no header.
2. Confirmar que textos principais mudam.
3. Confirmar que nao aparecem caracteres estranhos.
4. Confirmar frases comerciais da homepage em cada idioma.

## 9. Teste mobile e navegadores

1. Testar Chrome desktop.
2. Testar Edge desktop.
3. Testar mobile estreito.
4. Confirmar que header, botoes, cards, player, chat e formularios nao se sobrepoem.
5. Confirmar uploads e imagens em paginas publicas.

## 10. Criterios para falar com artista piloto

Avancar para um artista piloto quando:

1. Registo de musico, manager e fa nao tiver erros 500.
2. Pagamentos Stripe em modo teste estiverem completos.
3. Chat funcionar entre pelo menos dois utilizadores.
4. Admin conseguir entrar em qualquer stream.
5. Pagina publica do artista estiver visualmente apresentavel.
6. Existir um guiao simples para o artista preparar o YouTube.

## 11. Resultado esperado

No fim deste teste, deves conseguir provar o ciclo completo:

Empresa/manager cria artista, artista tem pagina publica, stream e acesso pago; fa entra, conversa no chat e envia gorjeta; admin consegue supervisionar tudo.
