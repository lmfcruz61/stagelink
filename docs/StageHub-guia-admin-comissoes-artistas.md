# StageHub - Guia admin de monetizacao e comissoes por artista

Este guia explica como configurar o modo de monetizacao e as comissoes personalizadas dos artistas na administracao da StageHub.

## Objetivo

A StageHub permite definir, por artista, como o artista monetiza a sua pagina e qual a comissao da plataforma.

## Modos de monetizacao

Cada artista tem um campo `Monetization mode`.

Existem 3 modos:

1. `Somente subscricao`
   - O publico subscreve o artista mensalmente.
   - O conteudo fica associado a subscricao.
   - A compra avulsa de material fica desativada.

2. `Subscricao e material pago exclusivo`
   - O publico pode subscrever o artista.
   - Apenas subscritores ativos podem comprar material pago.
   - Bom para conteudo premium e comunidade fechada.

3. `Somente material pago`
   - Nao ha subscricao ativa.
   - O publico compra eventos, videos ou galerias individualmente.
   - Bom para fotografos, eventos pontuais e vendas avulsas.

Por compatibilidade, artistas existentes ficam em `Somente material pago`, para nao bloquear vendas que ja estavam abertas.

Se um artista tiver subscricoes ativas, nao deve ser mudado para `Somente material pago` sem resolver primeiro essas subscricoes.

## Comissao StageHub

A StageHub tem uma comissao padrao de 20% sobre vendas. Em casos especiais, como o programa Artistas Fundadores, um artista pode ter uma comissao reduzida ou 0%.

Exemplos:

- `20.00` significa comissao padrao de 20%.
- `10.00` significa comissao reduzida de 10%.
- `0.00` significa sem comissao StageHub.

## Onde alterar

1. Entrar no painel de administracao.
2. Abrir `Accounts` > `Artists`.
3. Escolher o artista.
4. Procurar `Monetization mode`.
5. Escolher o modo correto.
6. Procurar `Commission rate`.
7. Definir a percentagem pretendida.
8. Guardar.

O campo aceita valores entre `0.00` e `100.00`.

## Quando a alteracao se aplica

A nova comissao aplica-se apenas a pagamentos criados depois da alteracao.

Pagamentos anteriores nao sao recalculados. Cada venda guarda a comissao usada no momento do checkout, para manter historico correto.

## Como afeta os pagamentos

Quando alguem compra bilhete, galeria, subscricao ou envia gorjeta:

1. A StageHub le a comissao configurada no artista.
2. Calcula a parte da plataforma.
3. Envia essa comissao para a StageHub via Stripe Connect.
4. O restante fica para o artista na conta Stripe ligada.

Exemplo com venda de `10 EUR`:

- Comissao `20.00`: StageHub recebe `2.00 EUR`; artista recebe `8.00 EUR`.
- Comissao `10.00`: StageHub recebe `1.00 EUR`; artista recebe `9.00 EUR`.
- Comissao `0.00`: StageHub recebe `0.00 EUR`; artista recebe `10.00 EUR`.

## Boas praticas

- Usar `20.00` como regra geral.
- Usar `0.00` apenas em acordos claros, por exemplo Artistas Fundadores.
- Registar internamente a razao para qualquer comissao especial.
- Confirmar sempre se o artista tem Stripe Connect ativo antes de testar vendas.

## Teste recomendado

Depois de alterar a comissao de um artista:

1. Criar uma venda pequena em ambiente real ou teste controlado.
2. Confirmar no dashboard StageHub os valores registados.
3. Confirmar no Stripe a comissao da plataforma e o valor liquido do artista.

## Notas importantes

- A comissao nao deve ser negativa.
- A comissao nao deve passar de 100%.
- A alteracao nao mexe em compras antigas.
- Para artistas convidados, a comissao pode ser alterada mais tarde sem alterar a estrutura do sistema.
