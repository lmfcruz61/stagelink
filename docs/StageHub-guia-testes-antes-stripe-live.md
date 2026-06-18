# StageHub - Guia de testes antes de ativar pagamentos live

Este guia serve para testar a StageHub antes de mudar Stripe para modo live.

Objetivo: validar tudo o que nao depende de dinheiro real primeiro, deixando os pagamentos reais para o fim.

## 1. Regra principal deste ciclo

Durante estes testes:

1. Manter Stripe em modo teste.
2. Nao usar cartoes reais.
3. Nao divulgar ainda o site como venda publica final.
4. Testar a experiencia como artista, publico e equipa.
5. So mudar para Stripe live depois de tudo o resto estar validado.

Dominio oficial:

`https://stagehub.pt/`

Dominio tecnico de apoio:

`https://stagelink.fly.dev/`

## 2. Preparacao antes dos testes

Confirmar:

1. O site abre em `https://stagehub.pt/`.
2. O site abre tambem em `https://www.stagehub.pt/`, se o DNS estiver configurado.
3. O login funciona.
4. O registo funciona.
5. O painel de artista abre.
6. O dashboard abre sem erros.
7. Nao aparecem mensagens tecnicas para o utilizador normal.

Resultado esperado:

1. Paginas carregam sem erro.
2. HTTPS aparece ativo.
3. Nao aparece erro de dominio, CSRF ou host.

## 3. Teste de conta de artista

Criar ou usar uma conta de artista.

Testar:

1. Entrar como artista.
2. Abrir dashboard.
3. Abrir `Editar pagina`.
4. Preencher nome artistico.
5. Preencher frase de destaque.
6. Preencher cidade/pais.
7. Preencher biografia.
8. Preencher email de contacto.
9. Preencher telefone de contacto.
10. Adicionar foto principal.
11. Adicionar imagem de capa.
12. Adicionar links oficiais, se existirem.
13. Guardar.

Resultado esperado:

1. Perfil guarda sem erro.
2. Foto aparece corretamente.
3. Capa aparece corretamente.
4. Email e telefone aparecem na pagina publica quando preenchidos.
5. Campos vazios nao deixam espacos estranhos na pagina publica.

## 4. Teste da pagina publica do artista

Abrir a pagina publica do artista.

Confirmar:

1. Nome do artista visivel.
2. Foto principal visivel.
3. Capa visivel.
4. Bio legivel.
5. Cidade/pais visivel, se preenchido.
6. Contactos visiveis, se preenchidos.
7. Links oficiais funcionam.
8. Botao de subscricao aparece.
9. Area de eventos aparece.
10. Biblioteca de videos aparece.
11. Galeria aparece, se houver fotos.

Resultado esperado:

1. Pagina parece pronta para publico.
2. Nao ha referencias tecnicas desnecessarias.
3. Nao aparece YouTube como opcao principal da StageHub.

## 5. Teste de conta de publico

Criar ou usar uma conta de publico.

Testar:

1. Entrar no site.
2. Criar conta de publico.
3. Fazer logout.
4. Fazer login novamente.
5. Abrir pagina de artista.
6. Adicionar artista aos favoritos.
7. Remover artista dos favoritos.
8. Abrir pagina de evento.

Resultado esperado:

1. Conta de publico consegue navegar.
2. Favoritos funcionam.
3. Conta de publico consegue ver eventos e artistas.
4. Conta de publico nao consegue aceder a ferramentas de artista.

## 6. Teste de criacao de evento pago

Entrar como artista ou equipa.

Criar um evento ao vivo:

1. Abrir dashboard.
2. Clicar em `Novo evento`.
3. Escolher artista.
4. Preencher titulo.
5. Preencher descricao.
6. Adicionar capa.
7. Escolher tipo `Ao vivo`.
8. Definir preco igual ou superior a 2 EUR.
9. Definir data e hora futura.
10. Guardar.

Testar tambem:

1. Tentar criar evento com preco 0 EUR.
2. Tentar criar evento com preco 1,99 EUR.

Resultado esperado:

1. Evento com 2 EUR ou mais guarda.
2. Evento com preco abaixo de 2 EUR e bloqueado.
3. Nao existem eventos gratuitos publicados.

## 7. Teste de configuracao OBS

Entrar como artista ou equipa.

Testar:

1. Abrir `Editar pagina`.
2. Confirmar se existe canal ao vivo.
3. Se nao existir, criar canal ao vivo.
4. Copiar `Servidor OBS`.
5. Copiar `Chave de transmissao`.
6. Abrir OBS.
7. Configurar servico personalizado.
8. Colar servidor.
9. Colar chave.
10. Iniciar transmissao de teste.

Resultado esperado:

1. OBS consegue iniciar transmissao.
2. A sala do evento mostra video.
3. Audio funciona.
4. Dados de OBS nao aparecem ao publico.

## 8. Teste da sala ao vivo

Com um evento criado:

1. Entrar como artista.
2. Abrir sala.
3. Confirmar player.
4. Confirmar estado do evento.
5. Confirmar contador de espectadores.
6. Confirmar chat.
7. Entrar como publico noutra janela/browser.
8. Confirmar que publico sem bilhete nao entra livremente.

Resultado esperado:

1. Artista consegue testar sala.
2. Publico sem acesso e encaminhado para compra/acesso.
3. Chat nao rebenta layout.
4. Video fica bem em desktop e mobile.

## 9. Teste de video gravado

Entrar como artista ou equipa.

Criar video gravado:

1. Abrir dashboard.
2. Clicar em `Novo video`.
3. Preencher titulo.
4. Preencher descricao.
5. Adicionar capa.
6. Definir preco igual ou superior a 2 EUR.
7. Definir duracao ate 60 minutos.
8. Guardar.
9. Fazer upload do ficheiro.
10. Aguardar fim do upload.
11. Confirmar estado de upload recebido.
12. Abrir sala.

Testar limite:

1. Tentar configurar video com duracao superior a 60 minutos.
2. Tentar upload de video superior a 1 hora, se existir ficheiro de teste.

Resultado esperado:

1. Video ate 1 hora e aceite.
2. Video acima de 1 hora e bloqueado.
3. O artista consegue perceber se o upload foi recebido.
4. O video fica associado ao evento/video correto.

## 10. Teste de biblioteca de videos

Na pagina publica do artista:

1. Abrir `Biblioteca de videos`.
2. Confirmar video criado.
3. Confirmar titulo.
4. Confirmar capa.
5. Confirmar preco.
6. Abrir video.

Resultado esperado:

1. Video aparece na biblioteca.
2. Publico sem acesso nao ve conteudo pago sem comprar.
3. Artista consegue editar video.

## 11. Teste de galerias de fotos pagas

Entrar como artista ou equipa.

Criar galeria:

1. Abrir dashboard.
2. Clicar em `Nova galeria`.
3. Preencher titulo.
4. Preencher descricao.
5. Adicionar capa publica discreta.
6. Definir preco igual ou superior a 2 EUR.
7. Marcar conteudo sensivel/adulto, se aplicavel.
8. Guardar.
9. Adicionar fotos privadas.
10. Confirmar limite de 30 fotos por galeria.
11. Confirmar limite de 10 fotos por envio.
12. Confirmar limite de 3 MB por foto.
13. Confirmar limite de 30 MB por envio.
14. Confirmar formatos JPG, PNG ou WebP.
15. Enviar para validacao.

Testar moderacao:

1. Entrar no admin Django.
2. Abrir galerias pendentes.
3. Aprovar uma galeria.
4. Rejeitar uma galeria de teste com motivo.
5. Confirmar que galerias pendentes/rejeitadas nao aparecem ao publico.
6. Confirmar que galerias aprovadas e ativas aparecem na pagina do artista.

Testar acesso:

1. Abrir galeria como publico sem compra.
2. Confirmar que so aparece capa publica, titulo, preco e numero de fotos.
3. Confirmar que fotos privadas nao aparecem.
4. Comprar acesso em modo teste.
5. Confirmar que as fotos privadas aparecem depois da compra.

Resultado esperado:

1. Publico nao pagante nao ve fotos privadas.
2. Comprador ve fotos privadas.
3. Galerias sensiveis mostram aviso.
4. Galerias so vendem depois de aprovadas.
5. Limites de tamanho impedem uploads demasiado pesados.

## 12. Teste de subscricoes em modo teste

Ainda com Stripe em modo teste:

1. Entrar como publico.
2. Abrir pagina do artista.
3. Escolher plano `Subscritor`.
4. Fazer pagamento com cartao de teste Stripe.
5. Confirmar retorno ao site.
6. Confirmar mensagem de subscricao.
7. Repetir com `Subscritor Pro`, se necessario.

Resultado esperado:

1. Checkout de teste abre.
2. Pagamento de teste confirma.
3. Subscricao aparece como ativa.
4. Beneficios aparecem conforme esperado.

Nota: este teste ainda nao valida dinheiro real. Valida fluxo, permissoes e experiencia.

## 13. Teste de bilhete em modo teste

Ainda com Stripe em modo teste:

1. Entrar como publico.
2. Abrir evento pago.
3. Clicar em `Comprar bilhete`.
4. Pagar com cartao de teste Stripe.
5. Voltar ao site.
6. Confirmar acesso a sala.
7. Confirmar que o bilhete fica associado a conta.
8. Fazer logout/login e confirmar que o acesso continua.

Resultado esperado:

1. Compra de teste conclui.
2. Publico entra na sala.
3. Compra fica guardada.
4. Nao e preciso comprar duas vezes.

## 14. Teste de gorjeta em modo teste

Ainda com Stripe em modo teste:

1. Entrar como publico com acesso ao evento.
2. Abrir sala.
3. Enviar gorjeta.
4. Usar cartao de teste Stripe.
5. Confirmar retorno ao evento.
6. Confirmar mensagem de sucesso.

Resultado esperado:

1. Gorjeta de teste confirma.
2. Valor fica registado.
3. Artista/equipa consegue ver impacto no dashboard, se aplicavel.

## 15. Teste Stripe Connect em modo teste

Antes de live, validar Connect em teste:

1. Entrar como artista/equipa.
2. Abrir `Editar pagina`.
3. Clicar em `Ligar Stripe`.
4. Completar onboarding de teste.
5. Confirmar estado ativo para pagamentos.
6. Fazer uma compra de bilhete em teste.
7. Confirmar no dashboard Stripe teste que ha divisao/comissao.

Resultado esperado:

1. Conta conectada de teste fica criada.
2. Artista fica pronto para cobrancas em teste.
3. Checkout usa Connect.
4. Comissao StageHub aparece corretamente.

Comissao atual:

1. StageHub: 20%.
2. Artista: 80%.

Exemplo:

1. Bilhete de 10 EUR.
2. StageHub: 2 EUR.
3. Artista: 8 EUR.

## 16. Testes que devem ficar para o fim

So fazer depois de tudo acima estar aprovado:

1. Mudar Stripe para live.
2. Configurar chaves live no Fly.
3. Confirmar webhook live, se estiver configurado.
4. Ligar conta real do artista.
5. Fazer compra real de valor baixo.
6. Confirmar pagamento real no Stripe.
7. Confirmar divisao real entre StageHub e artista.
8. Confirmar reembolso real, se decidires testar.

Recomendacao para primeiro pagamento real:

1. Criar evento privado/teste com preco minimo de 2 EUR.
2. Usar conta de publico controlada.
3. Comprar 1 bilhete.
4. Confirmar acesso.
5. Confirmar valor no Stripe.
6. Confirmar taxa/comissao.
7. Confirmar estado da conta conectada do artista.

## 17. Checklist antes de mudar para Stripe live

So avancar se tudo estiver marcado:

1. Dominio `stagehub.pt` funciona.
2. Login funciona.
3. Registo funciona.
4. Perfil de artista completo.
5. Contactos publicos funcionam.
6. Eventos pagos criam corretamente.
7. Eventos abaixo de 2 EUR sao bloqueados.
8. OBS testado.
9. Sala ao vivo testada.
10. Chat testado.
11. Video gravado testado.
12. Limite de 1 hora testado.
13. Biblioteca de videos testada.
14. Galerias pagas testadas.
15. Limites de 30 fotos por galeria, 10 fotos por envio, 3 MB por foto e 30 MB por envio testados.
16. Moderacao de galerias testada.
17. Subscricao teste funciona.
18. Bilhete teste funciona.
19. Gorjeta teste funciona.
20. Stripe Connect teste funciona.
21. Comissao de 20% confirmada em teste.
22. Pagina mobile aceitavel.
23. Guias PDF prontos para artista e publico.

## 18. O que mudar quando chegar a hora de live

Quando tudo estiver aprovado:

1. Trocar `STRIPE_SECRET_KEY` para chave live.
2. Trocar `STRIPE_PUBLISHABLE_KEY` para chave live, se usada no frontend.
3. Trocar webhook secret para live, se existir.
4. Confirmar que a conta Stripe principal esta em modo live.
5. Confirmar que o artista liga a sua propria conta real.
6. Fazer deploy/restart se necessario.
7. Fazer pagamento real pequeno.

Importante: contas conectadas reais sao criadas/completadas pelo artista ou pela equipa responsavel pelo artista, nao por uma conta falsa de teste.

## 19. Decisao final

So considerar a StageHub pronta para pagamentos live quando:

1. A experiencia sem pagamentos esta estavel.
2. A experiencia com pagamentos de teste esta estavel.
3. O artista sabe ligar Stripe.
4. O publico sabe comprar e entrar.
5. A equipa sabe verificar problemas.
6. A comissao esta confirmada.
7. Existe plano claro para suporte no primeiro evento real.

Se algum ponto falhar, corrigir antes de ativar pagamentos live.
