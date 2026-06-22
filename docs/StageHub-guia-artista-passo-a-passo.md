# StageHub - Guia do Artista

Este guia explica, passo a passo, como um artista usa a StageHub para vender eventos, receber pagamentos, transmitir ao vivo e publicar videos gravados.

## 1. O que e a StageHub

A StageHub e uma plataforma para artistas criarem eventos pagos, venderem bilhetes, receberem subscricoes mensais e aceitar gorjetas do publico.

Na pratica:

1. O artista cria ou recebe uma pagina publica.
2. Liga a sua conta Stripe para receber pagamentos.
3. Escolhe o modo de monetizacao.
4. Cria eventos, videos, galerias ou planos de subscricao conforme o modo escolhido.
5. Transmite ao vivo pelo OBS ou envia videos gravados.
6. O publico compra acesso, subscreve ou envia gorjetas.
7. A StageHub retira a comissao da plataforma e o restante fica para o artista.

## 2. Conta e pagina do artista

No dashboard, o artista deve completar a pagina publica:

1. Nome artistico.
2. Frase curta de apresentacao.
3. Cidade/pais.
4. Biografia.
5. Foto principal.
6. Imagem de capa.
7. Links oficiais, se existirem.
8. Fotos para a galeria.

Esta pagina e o espaco publico onde o publico ve os eventos, videos, links e planos de subscricao.

## 3. Escolher o modo de monetizacao

Antes de divulgar a pagina, o artista deve escolher como quer monetizar.

Existem 3 modos:

1. `Somente subscricao`
   - O publico paga uma subscricao mensal.
   - Os conteudos do artista ficam associados a essa subscricao.
   - Nao existe compra avulsa de material.

2. `Subscricao e material pago exclusivo`
   - O publico pode subscrever mensalmente.
   - O material pago fica exclusivo para subscritores ativos.
   - Ou seja, para comprar certos conteudos, a pessoa tem primeiro de ser subscritora.

3. `Somente material pago`
   - Nao existe subscricao ativa.
   - O publico compra apenas eventos, videos, galerias ou outros conteudos individualmente.
   - Este modo e indicado para fotografos, workshops, concertos pontuais ou vendas avulsas.

O modo pode ser alterado mais tarde, mas se existirem subscritores ativos nao se deve mudar para `Somente material pago` sem resolver primeiro essas subscricoes.

## 4. Configurar pagamentos com Stripe

Antes de vender bilhetes, receber subscricoes ou gorjetas, o artista tem de ligar pagamentos.

Passos:

1. Entrar no dashboard.
2. Abrir a pagina de edicao do artista.
3. Clicar em `Ligar Stripe`.
4. Seguir os passos da Stripe.
5. Preencher os dados pedidos pela Stripe.
6. Voltar a StageHub.
7. Confirmar que o estado aparece como ativo para receber pagamentos.

A StageHub cria o caminho de ligacao com a Stripe. O artista completa a conta com os seus dados. Em modo de teste, isto usa a Stripe de teste. Em producao, usa dados reais.

Se a conta Stripe do artista ainda nao estiver ativa, a StageHub bloqueia vendas pagas para esse artista.

## 5. Como os pagamentos sao divididos

A StageHub usa Stripe Connect para dividir pagamentos automaticamente.

Quando alguem paga:

1. O publico paga na Stripe.
2. A StageHub fica com a comissao da plataforma.
3. O restante fica destinado ao artista na sua conta Stripe.

A comissao combinada da StageHub e 20%.

Exemplos:

| Valor pago | Comissao StageHub | Valor do artista |
| --- | --- | --- |
| 2 EUR | 0,40 EUR | 1,60 EUR |
| 5 EUR | 1,00 EUR | 4,00 EUR |
| 10 EUR | 2,00 EUR | 8,00 EUR |
| 20 EUR | 4,00 EUR | 16,00 EUR |

Os valores podem ter arredondamentos normais da Stripe.

## 6. Quando e como o artista recebe

O pagamento ao artista e gerido pela Stripe.

Normalmente:

1. O dinheiro entra na conta Stripe conectada do artista.
2. A Stripe valida o pagamento.
3. A Stripe envia o valor disponivel para a conta bancaria configurada pelo artista.

O calendario de pagamento depende da Stripe, do pais, do tipo de conta e das verificacoes da conta.

A StageHub nao paga manualmente cada evento. A divisao e feita pela Stripe automaticamente.

## 7. Preco minimo dos eventos

Na StageHub, todos os eventos publicados sao pagos.

O preco minimo por bilhete e 2 EUR.

Este minimo existe para justificar custos de plataforma, video, pagamentos, processamento, suporte e rentabilidade do site.

Recomendacao:

1. Eventos pequenos/testes: minimo 2 EUR.
2. Concertos online curtos: 5 EUR a 10 EUR.
3. Concertos especiais, estreias ou acesso exclusivo: 10 EUR ou mais.

## 8. Criar um evento pago

No dashboard:

1. Escolher o artista.
2. Clicar em `Novo evento`.
3. Escrever titulo.
4. Adicionar descricao.
5. Adicionar capa horizontal.
6. Escolher tipo de conteudo:
   - `Ao vivo`;
   - `Estreia`;
   - `Video gravado`;
   - `Replay`.
7. Definir preco, sempre igual ou superior a 2 EUR.
8. Definir data e hora.
9. Definir duracao estimada.
10. Guardar.
11. Testar a sala.
12. Ativar quando estiver pronto.

Eventos gratuitos nao estao disponiveis na StageHub.

## 9. Transmitir ao vivo com OBS

Para eventos ao vivo, o artista usa OBS.

Preparacao:

1. No perfil do artista, clicar em `Criar canal ao vivo`, se ainda nao existir.
2. Copiar os dados privados:
   - `Servidor OBS`;
   - `Chave de transmissao`.
3. Abrir o OBS.
4. Ir a `Definicoes > Transmissao`.
5. Em `Servico`, escolher `Personalizado`.
6. Colar o `Servidor OBS` no campo `Servidor`.
7. Colar a `Chave de transmissao` no campo `Chave de transmissao`.
8. Clicar em `Aplicar`.
9. Clicar em `OK`.

Importante: o servidor e a chave nao devem ser partilhados publicamente.

## 10. Definicoes recomendadas no OBS

Para reduzir problemas, usar definicoes simples:

Video:

1. Resolucao: 1280x720.
2. FPS: 30.
3. Bitrate: cerca de 2500 Kbps.

Audio:

1. Bitrate: 128 Kbps ou 160 Kbps.
2. Confirmar que o microfone mexe no misturador de audio.

Se o computador for fraco, escolher codificador `Software (x264)`.

## 11. Antes de abrir o evento ao publico

Antes de divulgar:

1. Entrar na sala como artista.
2. Confirmar que o video aparece.
3. Confirmar que o audio funciona.
4. Confirmar que o chat funciona.
5. Confirmar que o contador `a ver` aparece.
6. Fazer uma compra de teste, se estiver em modo teste.
7. Confirmar que a conta Stripe do artista esta ativa.
8. Confirmar que o evento esta com preco correto.

So depois disso o link deve ser partilhado.

## 12. Videos gravados

A StageHub tambem permite videos gravados.

Passos:

1. No dashboard, escolher o artista.
2. Clicar em `Novo video`.
3. Preencher titulo, descricao, capa, data e preco.
4. Confirmar que o preco e pelo menos 2 EUR.
5. Guardar.
6. Enviar o ficheiro de video na area `Upload do video`.
7. Esperar o upload terminar.
8. Confirmar o estado `Upload recebido`.
9. Entrar em `Ver sala` para testar.
10. Ativar o video quando estiver pronto.

## 13. Limite de duracao dos videos

Videos gravados e replays nao podem ultrapassar 1 hora.

Regra:

1. Maximo: 60 minutos.
2. Ficheiros acima de 1 hora sao recusados.
3. A duracao estimada tambem deve ficar ate 60 minutos.

Este limite ajuda a controlar custos, qualidade da experiencia e rentabilidade da plataforma.

## 14. Subscricoes

O publico pode apoiar um artista com subscricao mensal quando o artista escolhe um modo que inclui subscricoes.

Planos atuais:

1. Subscritor: 5 EUR por mes.
2. Subscritor Pro: 10 EUR por mes.

Beneficios:

1. Acesso ao arquivo recente dos ultimos 30 dias.
2. Participacao no chat durante lives.
3. No plano Pro, desconto em bilhetes de lives pagas, quando aplicavel.

As subscricoes tambem passam pela Stripe e seguem a mesma regra de comissao da StageHub.

Se o artista escolher `Somente material pago`, a area de subscricao fica desativada.

## 15. Gorjetas

Em eventos pagos, o publico pode enviar gorjetas.

O processo e simples:

1. Publico escolhe o valor.
2. Escreve uma mensagem opcional.
3. Paga pela Stripe.
4. A StageHub retira a comissao.
5. O restante fica para o artista.

## 16. Galerias de fotos pagas

A StageHub tambem permite galerias de fotos pagas para fotografos, artistas e conteudo exclusivo.

Regras principais:

1. A galeria tem uma capa publica discreta.
2. As fotos privadas so aparecem depois de compra, subscricao ou acesso permitido pelo modo do artista.
3. O preco minimo e 2 EUR.
4. Cada galeria pode ter no maximo 30 fotos.
5. Cada envio pode ter no maximo 10 fotos de cada vez.
6. Cada foto pode ter no maximo 3 MB.
7. Cada envio pode ter no maximo 30 MB no total.
8. Formatos aceites: JPG, PNG e WebP.
9. Galerias sensiveis/adultas devem ser marcadas como conteudo sensivel.
10. A galeria tem de ser enviada para validacao StageHub.
11. So galerias aprovadas e ativas aparecem ao publico.

Passos:

1. No dashboard, clicar em `Nova galeria`.
2. Preencher titulo, descricao, capa publica e preco.
3. Marcar conteudo sensivel/adulto, se aplicavel.
4. Guardar a galeria.
5. Adicionar fotos privadas.
6. Enviar para validacao.
7. Aguardar aprovacao StageHub.
8. Ativar quando estiver pronta para venda.

## 17. Checklist rapido do artista

Antes do primeiro evento, confirmar:

1. Pagina publica completa.
2. Modo de monetizacao escolhido.
3. Stripe ligado e ativo.
4. Evento criado com preco minimo de 2 EUR, quando houver compra avulsa.
5. Video StageHub configurado.
6. OBS testado, se for ao vivo.
7. Video enviado, se for gravado.
8. Galeria validada, se houver fotos exclusivas.
9. Sala testada.
10. Chat testado.
11. Link publico copiado.
12. Evento ativado.

## 18. Suporte

Se algo falhar:

1. Nao apagar o evento.
2. Tirar screenshot do erro.
3. Dizer qual artista, evento e hora do problema.
4. Contactar o suporte StageHub.

O suporte StageHub consegue rever configuracao, pagamentos, estado do video e acesso ao evento.
