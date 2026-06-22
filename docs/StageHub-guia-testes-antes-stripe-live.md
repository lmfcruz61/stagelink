# StageHub - Guia de testes antes de pagamentos reais Stripe

Este guia serve para validar a StageHub antes de abrir pagamentos reais ao publico.

## 1. Antes de mudar chaves Stripe

Confirmar:

1. Site abre sem erros.
2. Login e recuperacao de password funcionam.
3. Pagina do artista esta completa.
4. Stripe Connect do artista esta ativo.
5. Videos por upload funcionam.
6. Galerias funcionam e passam por validacao.
7. Politicas legais e cookies estao acessiveis.

## 2. Teste de video

1. Criar `Novo video`.
2. Preencher dados e preco minimo de 2 EUR.
3. Guardar.
4. Fazer upload de um ficheiro com menos de 1 hora.
5. Confirmar `Upload recebido`.
6. Abrir a sala e testar o player.
7. Ativar o video.

## 3. Teste de galeria

1. Criar `Nova galeria`.
2. Adicionar capa publica discreta.
3. Adicionar fotos privadas.
4. Enviar para validacao.
5. Aprovar no admin.
6. Confirmar que aparece ao publico.
7. Confirmar que fotos privadas so aparecem depois de acesso.

## 4. Teste de pagamentos

1. Confirmar `STRIPE_SECRET_KEY`.
2. Confirmar `STRIPE_PUBLISHABLE_KEY`, se usada.
3. Confirmar webhook Stripe.
4. Fazer compra real pequena, por exemplo 2 EUR.
5. Confirmar pagamento na StageHub.
6. Confirmar valor no painel Stripe.
7. Confirmar comissao StageHub.
8. Confirmar liquido estimado do artista.

## 5. Teste de reembolso

1. Abrir o pagamento no Stripe.
2. Fazer reembolso, se necessario.
3. Confirmar que a equipa sabe identificar a compra na StageHub.

## 6. Checklist final

So avancar quando:

1. Compra real pequena funciona.
2. Stripe Connect do artista esta correto.
3. Webhook nao mostra falhas.
4. Conteudo comprado fica acessivel.
5. Conteudo nao comprado fica bloqueado.
6. Admin consegue ver mensagens, galerias, videos e pagamentos.

Se algum ponto falhar, corrigir antes de divulgar a plataforma.
