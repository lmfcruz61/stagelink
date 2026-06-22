# StageHub - Guia de Testes Passo a Passo

Ambiente sugerido: `https://stagehub.pt/` em producao controlada ou ambiente Fly de teste, com Stripe configurado no modo pretendido.

## 1. Preparacao

1. Abrir o site.
2. Entrar no admin em `/admin/`.
3. Confirmar que existe pelo menos um utilizador admin ativo.
4. Confirmar `Aparencia do site`: nome, logotipo, imagem de fundo e overlay.
5. Confirmar variaveis do Fly.io: `SECRET_KEY`, `DATABASE_URL`, Stripe, email e Cloudflare Stream.
6. Confirmar que o artista nao precisa de entrar em servicos externos de video.

## 2. Teste como admin

1. Entrar como admin.
2. Abrir homepage e confirmar header, logo, fundo e textos.
3. Abrir `/admin/`.
4. Verificar Users, Artists, Eventos, Galerias, Payments, Subscriptions, Tips e Site Appearance.
5. Confirmar que o admin consegue abrir conteudos para apoio/teste.
6. Confirmar que galerias pendentes aparecem para aprovacao.
7. Confirmar que a area Media Cloudflare lista videos associados.

## 3. Teste como artista

1. Criar ou abrir uma conta de artista.
2. Entrar no dashboard.
3. Confirmar botoes principais: `Editar pagina`, `Nova galeria` e `Novo video`.
4. Abrir `Editar pagina`.
5. Completar nome artistico, frase, cidade, bio, foto principal, capa, contactos e links.
6. Guardar e abrir a pagina publica.
7. Confirmar que a pagina publica esta clara e sem instrucoes tecnicas.

## 4. Teste de pagamentos Stripe

1. No dashboard do artista, clicar em `Ligar Stripe` ou `Abrir painel Stripe`.
2. Confirmar que o estado aparece como ligado, em validacao ou ativo.
3. Confirmar que vendas so ficam disponiveis quando a Stripe permite cobrancas.
4. Fazer uma compra pequena, se estiveres em ciclo de teste real controlado.
5. Confirmar receita bruta, comissao StageHub e liquido estimado no dashboard.
6. Confirmar os valores reais no painel Stripe.

## 5. Teste de upload de video

1. No dashboard, clicar em `Novo video`.
2. Preencher titulo, descricao, capa, preco, data e duracao estimada.
3. Confirmar que o tipo visivel e `Video gravado` ou `Replay`.
4. Confirmar que `Preparar upload de video` esta ativo.
5. Guardar.
6. Confirmar que aparece a area `Upload do video`.
7. Escolher um ficheiro de video com menos de 1 hora.
8. Clicar em `Enviar video`.
9. Aguardar a barra de progresso.
10. Confirmar estado `Upload recebido`.
11. Confirmar que aparece o codigo do video.
12. Abrir `Ver sala` e testar o player.
13. Ativar o video quando estiver pronto.

Teste negativo:

1. Tentar enviar um video com mais de 1 hora.
2. Confirmar que a StageHub recusa o ficheiro.
3. Confirmar que o artista entende a mensagem de erro.

## 6. Teste de biblioteca de videos

1. Abrir a pagina publica do artista.
2. Confirmar que existe a secao `Biblioteca de videos`.
3. Confirmar que videos ativos aparecem.
4. Confirmar que videos inativos nao aparecem ao publico.
5. Abrir um video como publico sem compra.
6. Confirmar que aparece bloqueio de acesso quando for pago.
7. Comprar acesso ou usar uma conta com permissao.
8. Confirmar que o video fica disponivel.

## 7. Teste de galerias

1. No dashboard, clicar em `Nova galeria`.
2. Preencher titulo, descricao, capa publica discreta e preco.
3. Marcar `Conteudo sensivel/adulto`, se aplicavel.
4. Guardar.
5. Adicionar fotos privadas.
6. Confirmar limites: 10 fotos por envio, 30 fotos por galeria, 3 MB por foto e 30 MB por envio.
7. Enviar para validacao.
8. Entrar como admin e aprovar.
9. Confirmar que a galeria aparece automaticamente na pagina publica.
10. Confirmar que fotos privadas ficam bloqueadas antes da compra.
11. Confirmar que fotos sensiveis aparecem protegidas/mascaradas antes do acesso.

## 8. Teste de modos de monetizacao

1. No admin, abrir o artista.
2. Confirmar o modo de monetizacao:
   - `Somente subscricao`;
   - `Subscricao e material pago exclusivo`;
   - `Somente material pago`.
3. Confirmar que o publico ve apenas as opcoes coerentes com esse modo.
4. Confirmar que o modo `Somente material pago` nao mostra subscricoes novas.
5. Confirmar que o modo exclusivo exige subscricao antes de compra de material pago.

## 9. Teste como publico

1. Criar ou usar uma conta de publico.
2. Abrir a homepage.
3. Abrir a pagina de um artista.
4. Comprar ou tentar aceder a um video pago.
5. Comprar ou tentar aceder a uma galeria paga.
6. Confirmar mensagens de bloqueio, compra e sucesso.
7. Confirmar email de recuperacao de password, se necessario.
8. Confirmar links legais e banner de cookies.

## 10. Teste mobile e navegadores

1. Testar Chrome desktop.
2. Testar Edge desktop.
3. Testar mobile estreito.
4. Confirmar que botoes, cards, imagens, formularios e player nao se sobrepoem.
5. Confirmar uploads em desktop.

## 11. Criterios para falar com artista piloto

Avancar quando:

1. Registo e login funcionam.
2. Stripe Connect esta ativo para o artista.
3. Upload de video funciona.
4. Limite de 1 hora funciona.
5. Galerias funcionam e passam por validacao.
6. Compras pagas funcionam.
7. Admin consegue supervisionar conteudos.
8. A pagina publica do artista esta apresentavel.

## 12. Resultado esperado

No fim do teste, deves conseguir provar o ciclo completo:

Artista cria pagina, liga Stripe, publica video ou galeria, publico compra acesso, pagamento e comissao ficam registados, e o admin consegue acompanhar tudo.
