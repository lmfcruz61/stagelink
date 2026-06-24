# StageHub - Checklist de Testes do Site

Data sugerida do teste: ____ / ____ / ______

Ambiente:

- [x] Producao: https://stagehub.pt/
- [ ] Utilizador admin disponivel
- [ ] Conta de artista disponivel
- [ ] Conta de publico disponivel
- [x] Stripe em modo correto para o teste

## 1. Acesso geral

- [x] A homepage abre sem erro.
- [x] O site responde em `https://stagehub.pt/`.
- [ ] O logo aparece corretamente.
- [ ] A imagem de fundo aparece corretamente.
- [ ] O menu/header aparece corretamente em desktop.
- [ ] O menu/header aparece corretamente em mobile.
- [x] O rodape esta visivel.
- [x] Links do rodape funcionam:
  - [ ] Recuperar password
  - [x] Privacidade
  - [x] Cookies
  - [x] Termos
  - [x] Contactar-nos
  - [x] Gerir cookies

## 2. Conta e login

- [ ] Registo de novo utilizador funciona.
- [x] Registo bloqueia email ja usado noutra conta.
- [x] Registo normaliza email para minusculas.
- [ ] Login funciona.
- [ ] Logout funciona.
- [ ] Recuperacao de password envia email.
- [ ] Link de recuperacao permite definir nova password.
- [ ] Login com password nova funciona.
- [x] Utilizador sem login nao acede ao dashboard.

## 3. Cookies e RGPD

- [ ] Banner de cookies aparece na primeira visita.
- [ ] Botao `Aceitar` guarda consentimento.
- [ ] Botao `Rejeitar` guarda escolha.
- [ ] Botao `Configurar` abre opcoes.
- [ ] `Gerir cookies` no rodape volta a abrir preferencias.
- [ ] Banner nao reaparece depois de guardar escolha.
- [x] Paginas legais abrem corretamente.

## 4. Pagina do artista

- [ ] Pagina publica do artista abre.
- [ ] Nome artistico aparece corretamente.
- [ ] Frase de destaque aparece.
- [ ] Bio aparece.
- [ ] Cidade/pais aparece.
- [ ] Foto principal aparece.
- [ ] Capa aparece.
- [ ] Email de contacto aparece, se definido.
- [ ] Telefone aparece, se definido.
- [ ] Links externos aparecem, se definidos.
- [ ] A pagina fica bem em mobile.

## 5. Dashboard do artista

- [x] Dashboard abre para o artista.
- [ ] Botao `Editar pagina` funciona.
- [ ] Botao `Nova galeria` funciona.
- [ ] Botao `Novo video` funciona.
- [x] Estado Stripe aparece corretamente.
- [x] Modo de monetizacao aparece corretamente.
- [x] Resumo financeiro aparece sem erro.
- [x] Conteudos do artista aparecem na lista.

## 6. Upload de fotos simples do artista

- [x] Artista consegue abrir `Editar pagina`.
- [ ] Upload de foto principal funciona.
- [ ] Upload de capa funciona.
- [x] Upload de fotos simples da pagina funciona.
- [ ] Fotos simples aparecem na pagina publica.
- [x] Upload com ficheiro demasiado grande mostra erro claro.
- [ ] Upload com formato invalido mostra erro claro.
- [x] Upload de muitas fotos mostra erro claro.

## 7. Galerias pagas

- [ ] Artista consegue criar `Nova galeria`.
- [ ] Titulo da galeria guarda corretamente.
- [ ] Descricao guarda corretamente.
- [ ] Capa publica guarda corretamente.
- [x] Preco minimo de 2 EUR e aplicado.
- [ ] Galeria sensivel/adulta pode ser marcada.
- [ ] Fotos privadas podem ser adicionadas.
- [x] Limite de 10 fotos por envio funciona.
- [x] Limite de 3 MB por foto funciona.
- [x] Limite de 30 MB por envio funciona.
- [ ] Galeria pode ser enviada para validacao.
- [x] Galeria pendente aparece no admin.
- [x] Admin consegue aprovar galeria.
- [x] Galeria aprovada aparece ao publico.
- [ ] Galeria rejeitada nao aparece ao publico.
- [x] Fotos privadas nao aparecem antes da compra.
- [x] Fotos privadas aparecem depois de acesso pago.

## 8. Videos

- [ ] Artista consegue clicar em `Novo video`.
- [x] Formulario de video abre.
- [x] Titulo guarda corretamente.
- [ ] Descricao guarda corretamente.
- [ ] Capa guarda corretamente.
- [x] Preco minimo de 2 EUR e aplicado.
- [x] Data e duracao guardam corretamente.
- [x] Area `Upload do video` aparece depois de guardar.
- [ ] Upload de video com menos de 1 hora funciona.
- [ ] Estado muda para `Upload recebido`.
- [ ] Codigo do video aparece.
- [ ] Video aparece na biblioteca do artista.
- [ ] Video pode ser testado em `Ver sala`.
- [ ] Video pode ser ativado.
- [x] Video com mais de 1 hora e recusado.
- [ ] Falha de upload mostra mensagem clara.

## 9. Lives e OBS

- [x] Botao `Nova live` aparece para artista/gestor.
- [x] Formulario de live abre.
- [x] Formulario de live nao exige ID manual de video.
- [x] Nova live abre com preco inicial de 2 EUR.
- [x] Preco minimo de 2 EUR e aplicado a lives novas e antigas.
- [x] Criar live prepara ou reutiliza canal ao vivo do artista.
- [x] Edicao de live mostra o canal StageHub ligado.
- [x] Dados OBS aparecem na edicao da live quando disponiveis.
- [x] Live sem dados OBS mostra botao `Preparar dados OBS`.
- [x] Configuracao OBS recomendada aparece:
  - [x] 1280x720
  - [x] 30 FPS
  - [x] Bitrate 4000-6000 kbps
  - [x] Keyframe 2 segundos
  - [x] x264 veryfast
- [x] Live agendada mantem contagem decrescente na sala.
- [x] Live ativa mostra badge vermelho `Ao vivo`.
- [x] Botao `Ativar live` aparece na edicao da live gravada.
- [x] Data/hora da live aparece em formato local na edicao.
- [ ] Teste real com OBS envia imagem/som para a sala.
- [ ] Publico consegue entrar e assistir live real apos pagamento.

## 10. Stripe Connect do artista

- [x] Botao `Ligar Stripe` aparece quando conta nao esta ligada.
- [ ] Botao abre fluxo Stripe.
- [x] Depois da ligacao, estado muda para conta ligada/em validacao/ativa.
- [x] Botao passa a `Abrir painel Stripe` quando aplicavel.
- [x] Artista consegue consultar painel Stripe.
- [x] Dashboard mostra cobrancas ativas quando Stripe permite.
- [x] Dashboard mostra pagamentos ao banco ativos quando Stripe permite.

## 11. Pagamentos do publico

- [x] Publico sem acesso ve bloqueio em video pago.
- [x] Publico consegue iniciar compra de video.
- [x] Checkout Stripe abre.
- [ ] Pagamento concluido devolve ao site.
- [ ] Acesso ao video fica ativo apos pagamento.
- [x] Publico sem acesso ve bloqueio em galeria paga.
- [x] Publico consegue comprar galeria.
- [x] Acesso a galeria fica ativo apos pagamento.
- [x] Gorjeta funciona, se disponivel.
- [x] Subscricao funciona, se o modo do artista permitir.

## 12. Comissoes

- [x] Artista com comissao 20% calcula valores corretamente.
- [x] Artista com comissao 10% calcula valores corretamente.
- [x] Artista com comissao 0% calcula valores corretamente.
- [x] Dashboard mostra receita bruta.
- [x] Dashboard mostra comissao StageHub.
- [x] Dashboard mostra liquido estimado do artista.
- [x] Pagamentos antigos nao sao alterados por mudanca futura de comissao.

## 13. Modos de monetizacao

- [x] `Somente subscricao` nao mostra compra avulsa.
- [x] `Subscricao e material pago exclusivo` exige subscricao para material pago.
- [x] `Somente material pago` nao mostra subscricao ativa.
- [ ] Alterar modo no admin reflete na pagina publica.
- [x] Conteudos aparecem de forma coerente com o modo escolhido.

## 14. Admin

- [x] Admin Django abre.
- [ ] Admin consegue ver artistas.
- [x] Admin consegue editar comissao do artista.
- [x] Admin consegue ver galerias.
- [x] Admin consegue aprovar galerias.
- [ ] Admin consegue rejeitar galerias.
- [x] Admin consegue ver contactos recebidos.
- [x] Admin consegue marcar contacto como resolvido.
- [x] Admin consegue abrir Media Cloudflare.
- [x] Admin consegue ver videos associados.
- [x] Admin consegue apagar media quando necessario.
- [x] Logs de eliminacao ficam registados.

## 15. Contactos

- [x] Pagina `/contacto` abre.
- [x] Formulario exige nome.
- [x] Formulario exige email valido.
- [x] Formulario exige tipo de contacto.
- [x] Formulario exige assunto.
- [x] Formulario exige mensagem.
- [x] Contacto geral envia email.
- [x] Contacto financeiro envia email com prefixo correto.
- [x] Contacto tecnico envia email com prefixo correto.
- [x] Mensagem fica guardada na base de dados.
- [x] Admin consegue ver a mensagem.

## 16. Mobile

- [ ] Homepage funciona em mobile.
- [ ] Pagina do artista funciona em mobile.
- [ ] Dashboard funciona em mobile.
- [ ] Formularios funcionam em mobile.
- [ ] Upload de fotos mostra mensagens claras em mobile.
- [ ] Checkout Stripe funciona em mobile.
- [ ] Rodape fica legivel em mobile.

## 17. Erros e estabilidade

- [ ] Site nao mostra erro 502.
- [x] Site nao mostra erro 500.
- [x] Upload com erro nao deixa pagina sem explicacao.
- [x] Maquina Fly permanece ativa.
- [x] `https://stagehub.pt/` responde 200 OK.
- [x] Logs Fly nao mostram erros recentes.

## 18. Resultado final

- [ ] Artista consegue completar pagina.
- [ ] Artista consegue carregar fotos.
- [ ] Artista consegue criar galeria paga.
- [ ] Admin consegue aprovar galeria.
- [ ] Artista consegue carregar video.
- [ ] Publico consegue comprar acesso.
- [ ] Stripe regista pagamento.
- [ ] Dashboard mostra valores.
- [ ] Site esta pronto para novo teste com artista real.
