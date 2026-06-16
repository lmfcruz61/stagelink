# StageHub - Guia de Testes Passo a Passo

Ambiente sugerido para este ciclo: Fly.io em `https://stagelink.fly.dev/`, Stripe em modo teste e video StageHub configurado para eventos pagos.

## 1. Preparacao

1. Abrir `https://stagelink.fly.dev/`.
2. Entrar no admin em `/admin/`.
3. Confirmar que existe pelo menos um utilizador admin ativo.
4. No admin, configurar `Aparencia do site`: nome, logotipo, imagem de fundo e overlay.
5. Confirmar variaveis do Fly.io: `SECRET_KEY`, `DATABASE_URL`, chaves Stripe, Redis/Upstash quando for usado chat multi-instancia.
6. Confirmar que os servicos de video da plataforma estao configurados. O artista nao cria nem paga contas externas de video.

## 2. Teste como admin

1. Entrar como admin.
2. Abrir a homepage e confirmar header, logo, fundo e imagem de perfil.
3. Abrir `/admin/` e verificar Users, Artists, Organizations, Organization Members, Eventos, Subscriptions, Tips e Site Appearance.
4. Criar ou rever uma equipa/empresa.
5. Criar ou rever artistas associados a essa equipa.
6. Abrir uma sala de evento como admin. O admin deve entrar sem bilhete nem subscricao.
7. Confirmar que uploads de imagens aparecem no site publico.

## 3. Teste como artista individual

1. Criar conta nova como artista.
2. Entrar no dashboard.
3. Confirmar que nao aparecem botoes de equipa como `Nova equipa` ou `Novo artista gerido`.
4. Abrir o `Guia rapido`.
5. Editar pagina publica: nome artistico, frase, cidade, bio, foto principal, capa e links.
6. Adicionar varias fotos a galeria.
7. No perfil do artista, usar `Criar canal ao vivo` para gerar os dados de transmissao para OBS.
8. Criar evento com titulo, capa 16:9, tipo de conteudo, data futura e preco.
9. Confirmar que o evento tem preco maior que zero e usa video StageHub.
10. Para evento realmente em direto, escolher `Ao vivo`; para video preparado, escolher `Estreia` ou `Video gravado`; para conteudo passado ainda disponivel, escolher `Replay`.
11. Ativar o evento.
12. Abrir a pagina publica do artista e confirmar capa, foto, bio, links, galeria, evento agendado e evento ativo.
13. Entrar na sala como artista e confirmar countdown, player, badge do estado, marca do artista no video, chat, contador `a ver` e botoes de apoio.

## 4. Teste como manager / equipa

1. Criar conta de manager.
2. Entrar no dashboard.
3. Confirmar que aparecem `Nova equipa` e `Novo artista gerido`.
4. Criar `Nova equipa`.
5. Abrir a equipa e adicionar membros por username: Dono, Manager, Editor e Leitor.
6. Criar `Novo artista gerido` associado a equipa.
7. Selecionar o artista no dashboard.
8. Editar pagina publica desse artista.
9. Criar evento para esse artista e escolher o tipo correto: `Ao vivo`, `Estreia`, `Video gravado` ou `Replay`.
10. Depois de um evento terminado, editar o evento e mudar para `Replay` se o video continuar disponivel.
11. Entrar com outro membro da equipa e confirmar permissoes.
12. Confirmar que o manager consegue entrar na sala do evento para operar/testar.

## 5. Teste como publico

1. Criar conta nova como publico.
2. Confirmar avatar circular por defeito no header/perfil.
3. Atualizar nome publico e foto do perfil.
4. Abrir a homepage e o guia rapido para o publico.
5. Abrir pagina de um artista.
6. Confirmar que a secao `Subscricoes` aparece com planos de 5 EUR e 10 EUR.
7. Marcar e remover artista favorito.
8. Tentar entrar num evento pago sem acesso. Deve aparecer bloqueio.
9. Comprar bilhete em modo teste ou criar acesso/subscricao de teste.
10. Entrar na sala.
11. Confirmar que eventos aparecem com o estado correto: `Ao vivo`, `Estreia`, `Video gravado` ou `Replay disponivel`.
12. Enviar mensagem no chat e confirmar que aparece imediatamente.
13. Usar os botoes rapidos de emoji do chat.
14. Enviar gorjeta em modo teste.
15. Confirmar que a gorjeta aparece no dashboard do artista/manager.

## 6. Teste de pagamentos Stripe

1. Usar Stripe em modo teste.
2. No perfil do artista, clicar em `Ligar Stripe` e completar o onboarding de teste.
3. Confirmar que o estado do artista fica ativo para receber pagamentos.
4. Testar compra de bilhete one-time.
5. Testar subscricao mensal.
6. Testar gorjeta one-time.
7. Confirmar que a StageHub reteve a comissao configurada e o restante ficou destinado ao artista.
8. Confirmar estados no dashboard e no admin.
9. Confirmar comportamento se o pagamento for cancelado.
10. Confirmar comportamento se o pagamento falhar.

## 7. Teste de transmissao ao vivo

1. No perfil do artista, clicar em `Criar canal ao vivo`.
2. Confirmar que a StageHub guardou `Servidor OBS` e `Chave de transmissao`.
3. No OBS, configurar `Servico: Personalizado`, `Servidor` e `Chave de transmissao`.
4. Adicionar uma fonte no OBS, por exemplo webcam, captura de ecra ou ficheiro de video local.
5. Iniciar transmissao no OBS.
6. Abrir a sala StageHub e confirmar que o player aparece.
7. Confirmar que existe algum atraso normal em transmissao online.
8. Para video gravado, usar `Novo video`, preparar upload e enviar o ficheiro pela pagina do evento.
9. Testar em desktop e mobile.

Nota: a StageHub ja nao publica eventos gratuitos. Todos os eventos devem ter preco e podem receber gorjetas.

## 8. Teste de sala ao vivo, chat e presenca

1. Criar um evento marcado para daqui a 5 minutos e confirmar `Agendado` + countdown ao segundo.
2. Quando chegar a hora marcada, confirmar que o player aparece sem refresh manual.
3. Confirmar que um evento ja iniciado abre diretamente com o player.
4. Criar/testar eventos dos tipos `Ao vivo`, `Estreia`, `Video gravado` e `Replay`.
5. Confirmar que video gravado e replay nunca aparecem como `Ao vivo`.
6. Entrar na mesma sala com dois utilizadores diferentes.
7. Confirmar que ambos veem o player e o chat.
8. Confirmar que o contador `a ver` aparece junto ao titulo do evento e no cabecalho do chat.
9. Enviar texto normal, texto com acentos e texto com emojis.
10. Fechar uma das janelas e confirmar que a contagem reduz.
11. Recarregar a pagina e confirmar que o chat volta a ligar.

Nota: nesta fase piloto, o contador mede ligacoes ativas na sala. Em escala com varias maquinas Fly.io, deve passar para presenca partilhada via Redis/Upstash.

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
4. Contador `a ver` atualizar ao abrir/fechar uma segunda janela.
5. Admin conseguir entrar em qualquer evento.
6. Pagina publica do artista estiver visualmente apresentavel.
7. Existir um guiao simples para o artista preparar OBS.
8. Estados dos eventos aparecerem corretamente: agendado, ao vivo, estreia, video gravado e replay.

## 11. Resultado esperado

No fim deste teste, deves conseguir provar o ciclo completo:

Empresa/manager cria artista, artista tem pagina publica, evento com tipo correto e acesso pago; publico entra, ve countdown/player com marca do artista, conversa no chat, usa emojis, ve a contagem de espectadores, subscreve e envia gorjeta; admin consegue supervisionar tudo.
