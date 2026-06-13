# StageHub - Guia OBS para transmitir ao vivo

Este guia serve para artistas, managers ou equipa tecnica transmitirem um espetaculo ao vivo para o StageHub usando OBS e Cloudflare Stream.

## 1. O que precisas antes de abrir o OBS

1. Uma conta de artista/equipa no StageHub.
2. Um `Live Input` criado pela StageHub no perfil do artista. O artista nao paga Cloudflare.
3. Estes dados fornecidos pela equipa StageHub:
   - `RTMPS URL`;
   - `Stream Key`;
   - `Live Input UID`.
4. O perfil do artista no StageHub com o `Live Input UID` guardado pela plataforma.
5. Um espetaculo criado no StageHub com:
   - plataforma de video `Cloudflare Stream`;
   - tipo de conteudo `Ao vivo`;
   - `ID do stream Cloudflare` preenchido automaticamente a partir do perfil do artista, ou confirmado manualmente;
   - data/hora correta;
   - espetaculo ativo.
6. Uma ligacao de internet estavel. Sempre que possivel, usar cabo de rede em vez de Wi-Fi.

## 2. Configurar a transmissao no OBS

1. Abrir o OBS.
2. Ir a `Definicoes > Transmissao`.
3. Em `Servico`, escolher `Personalizado`.
4. No campo `Servidor`, colar o `RTMPS URL` do Cloudflare.
5. No campo `Chave de transmissao`, colar a `Stream Key`.
6. Clicar em `Aplicar`.
7. Clicar em `OK`.

Importante: nao juntar o RTMPS URL e a Stream Key no mesmo campo. O URL vai no servidor; a key vai na chave.

## 3. Configurar o Live Input no Cloudflare

Esta parte e feita pela equipa StageHub, nao pelo artista. No Cloudflare, abrir o Live Input usado no StageHub:

1. Ir a `Media > Stream > Live inputs`, ou usar o botao `Criar Live Input` no perfil do artista no StageHub.
2. Abrir o Live Input do evento.
3. Em `Settings`, manter `Live Playback and Recording` ativo.
4. Ativar `Low-Latency HLS Support`, se estiver disponivel.
5. Para testes, ativar `Automatically Delete Recordings`.
6. Definir apagar gravacoes apos `1 day`, para nao acumular storage.
7. Clicar em `Save`.

Nota: `Live Playback and Recording` permite ver a live pelo player Cloudflare e tambem grava a transmissao. Se nao quiseres guardar testes, usa `Automatically Delete Recordings`.

## 4. Adicionar uma fonte de video

Se o OBS disser `sem fontes selecionadas`, faz isto:

1. Na caixa `Fontes`, clicar no botao `+`.
2. Escolher uma opcao:
   - `Dispositivo de captura de video` para webcam;
   - `Captura de ecra` para mostrar o ecra;
   - `Captura de janela` para mostrar uma janela especifica;
   - `Fonte multimidia` para transmitir um ficheiro de video local.
3. Confirmar que a imagem aparece no preview do OBS.

Para o primeiro teste, recomenda-se usar webcam ou um ficheiro de video local pequeno.

## 5. Adicionar e confirmar audio

No OBS, confirmar o `Misturador de audio`:

1. Falar para o microfone.
2. Confirmar que a barra `Mic/Aux` mexe.
3. Se quiseres transmitir som do computador, confirmar que `Audio do ambiente de trabalho` tambem mexe.

Se nao houver barras a mexer:

1. Ir a `Definicoes > Audio`.
2. Em `Audio global`, escolher o microfone correto em `Mic/Aux`.
3. Escolher a saida correta em `Audio do ambiente de trabalho`, se for necessaria.
4. Clicar em `Aplicar`.

No teste real, o Cloudflare deve mostrar `Encoding audio bitrate`. Se aparecer um valor perto de `128 kbit/s` ou `160 kbit/s`, o audio esta a chegar ao Cloudflare.

## 6. Definicoes recomendadas para MVP

Ir a `Definicoes > Video`:

1. Resolucao base: `1280x720`.
2. Resolucao de saida: `1280x720`.
3. FPS: `30`.

Ir a `Definicoes > Saida`:

1. Modo de saida: `Simples`.
2. Codificador: `Software (x264)`.
3. Bitrate de video: `2500 Kbps`.
4. Bitrate de audio: `128 Kbps` ou `160 Kbps`.

Se estiver em modo avancado:

1. Separador `Transmissao`.
2. Codificador: `x264`.
3. Keyframe interval: `2 s`.
4. Preset CPU: `veryfast`.
5. Bitrate: `2500 Kbps`.
6. Audio bitrate: `128 Kbps` ou `160 Kbps`.

Estas definicoes reduzem erros de encoder e ajudam em computadores menos potentes. Evita transmitir a `10 Mbit/s` no MVP, porque aumenta consumo, processamento e pode piorar buffering/latencia.

## 7. Iniciar transmissao

1. No OBS, clicar em `Iniciar transmissao`.
2. Abrir Cloudflare em `Media > Stream > Live inputs`.
3. Abrir o Live Input usado.
4. Confirmar que o estado muda de `Disconnected` para ligado/em direto.
5. Confirmar que existe `Ingress bitrate`.
6. Confirmar que existe `Encoding video bitrate`.
7. Confirmar que existe `Encoding audio bitrate`.
8. Esperar alguns segundos.
9. Abrir a sala do espetaculo no StageHub.
10. Confirmar que o player Cloudflare aparece.

Valores esperados para teste:

1. Video: cerca de `2.5 Mbit/s` a `3 Mbit/s`.
2. Audio: cerca de `128 kbit/s` a `160 kbit/s`.
3. FPS: `30`.

## 8. Se aparecer erro ao iniciar transmissao

Se o OBS mostrar erro sobre NVENC, AMD ou codificador:

1. Ir a `Definicoes > Saida`.
2. Trocar o codificador para `Software (x264)`.
3. Reduzir a resolucao para `1280x720`.
4. Manter FPS em `30`.
5. Tentar novamente.

Se continuar a falhar:

1. Confirmar que o `RTMPS URL` esta correto.
2. Confirmar que a `Stream Key` esta correta.
3. Confirmar que o Live Input nao foi apagado no Cloudflare.
4. Reiniciar o OBS.

## 9. Se nao houver audio na sala

1. Confirmar que o player/browser nao esta em mute.
2. Confirmar que o separador do browser nao esta silenciado.
3. Confirmar no OBS que a barra `Mic/Aux` mexe.
4. Confirmar no Cloudflare que existe `Encoding audio bitrate`.
5. Esperar a latencia da live antes de concluir que nao ha som.

Se o Cloudflare mostra audio bitrate, o audio esta a chegar. O problema pode estar no player em mute, no volume do browser ou na espera da latencia.

## 10. Latencia esperada

Cloudflare Stream com OBS usa RTMPS/HLS. Isto funciona para eventos assistidos, mas pode ter atraso visivel entre o artista e o publico.

Para o MVP:

1. Aceitar algum atraso em concertos, estreias e eventos com chat menos sincronizado.
2. Avisar o artista que as respostas do chat podem chegar com atraso.
3. Evitar formatos que dependam de perguntas/respostas ao segundo.

Para interacao quase imediata, sera necessario evoluir para WebRTC ou outra solucao de baixa latencia.

Para reduzir a latencia no MVP:

1. Ativar `Low-Latency HLS Support` no Cloudflare.
2. Usar `1280x720`.
3. Usar `30 FPS`.
4. Usar bitrate perto de `2500 Kbps`.
5. Usar keyframe interval de `2 s`.
6. Usar ligacao de internet estavel.

## 11. Checklist antes de abrir portas ao publico

1. OBS mostra imagem e audio.
2. Cloudflare Live Input esta ligado.
3. StageHub mostra o player na sala.
4. Chat liga e envia mensagens.
5. Contador `a ver` funciona.
6. Bilhete/subscricao bloqueia quem nao tem acesso.
7. Admin/artista conseguem entrar sem compra.
8. O artista sabe que existe latencia no modo RTMPS/HLS.
9. `Automatically Delete Recordings` esta ativo durante testes, se nao quiseres guardar videos.

## 12. Checklist rapido no dia do evento

1. Abrir OBS 30 minutos antes.
2. Confirmar microfone/camera.
3. Fazer teste privado no StageHub.
4. Confirmar Cloudflare ligado.
5. Confirmar sala StageHub com player.
6. Confirmar chat.
7. Comecar transmissao no horario combinado.
8. No fim, parar transmissao no OBS.
9. Se houver replay, editar o evento para `Replay`.
10. Se nao quiseres replay, confirmar que a gravacao sera apagada automaticamente no Cloudflare.
