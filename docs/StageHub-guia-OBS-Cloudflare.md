# StageHub - Guia OBS para transmitir ao vivo

Este guia serve para artistas transmitirem um evento ao vivo para a StageHub usando OBS.

## 1. O que precisas antes de abrir o OBS

1. Uma conta de artista no StageHub.
2. Um canal ao vivo criado pela StageHub no perfil do artista.
3. Estes dados privados fornecidos pela StageHub:
   - `Servidor OBS`;
   - `Chave de transmissao`.
4. Um evento criado no StageHub com:
   - plataforma de video `Video StageHub`;
   - tipo de conteudo `Ao vivo`;
   - data/hora correta;
   - evento ativo quando estiver pronto para publico.
5. Uma ligacao de internet estavel. Sempre que possivel, usar cabo de rede em vez de Wi-Fi.

## 2. Configurar a transmissao no OBS

1. Abrir o OBS.
2. Ir a `Definicoes > Transmissao`.
3. Em `Servico`, escolher `Personalizado`.
4. No campo `Servidor`, colar o `Servidor OBS` fornecido pela StageHub.
5. No campo `Chave de transmissao`, colar a `Chave de transmissao`.
6. Clicar em `Aplicar`.
7. Clicar em `OK`.

Importante: nao juntar o servidor e a chave no mesmo campo. O servidor vai no campo `Servidor`; a chave vai no campo `Chave de transmissao`.

## 3. Preparar o canal na StageHub

Esta parte e feita no dashboard da StageHub:

1. Abrir o perfil do artista.
2. Clicar em `Criar canal ao vivo`, se ainda nao existir.
3. Copiar os dados privados para OBS.
4. Criar ou editar o evento.
5. Confirmar tipo `Ao vivo` e video `Video StageHub`.
6. Guardar o evento.

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

Estas definicoes reduzem erros de encoder e ajudam em computadores menos potentes. Evita transmitir a `10 Mbit/s` no MVP, porque aumenta consumo, processamento e pode piorar buffering/latencia.

## 7. Iniciar transmissao

1. No OBS, clicar em `Iniciar transmissao`.
2. Esperar alguns segundos.
3. Abrir a sala do evento no StageHub.
4. Confirmar que o player aparece.
5. Confirmar que imagem e audio chegam ao publico.

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

1. Confirmar que o `Servidor OBS` esta correto.
2. Confirmar que a `Chave de transmissao` esta correta.
3. Reiniciar o OBS.
4. Pedir ao suporte StageHub para recriar o canal ao vivo do artista, se necessario.

## 9. Se nao houver audio na sala

1. Confirmar que o player/browser nao esta em mute.
2. Confirmar que o separador do browser nao esta silenciado.
3. Confirmar no OBS que a barra `Mic/Aux` mexe.
4. Esperar a latencia normal da transmissao antes de concluir que nao ha som.
5. Testar com headphones para evitar eco.

## 10. Latencia esperada

Transmissao por OBS pode ter atraso visivel entre o artista e o publico. Isto e normal nesta fase piloto.

Para o MVP:

1. Aceitar algum atraso em concertos, estreias e eventos com chat menos sincronizado.
2. Avisar o artista que as respostas do chat podem chegar com atraso.
3. Evitar formatos que dependam de perguntas/respostas ao segundo.

## 11. Checklist antes de abrir portas ao publico

1. OBS mostra imagem e audio.
2. StageHub mostra o player na sala.
3. Chat liga e envia mensagens.
4. Contador `a ver` funciona.
5. Bilhete/subscricao bloqueia quem nao tem acesso.
6. Admin/artista conseguem entrar sem compra.
7. O artista sabe que existe latencia normal em transmissao online.

## 12. Checklist rapido no dia do evento

1. Abrir OBS 30 minutos antes.
2. Confirmar microfone/camera.
3. Fazer teste privado no StageHub.
4. Confirmar sala StageHub com player.
5. Confirmar chat.
6. Comecar transmissao no horario combinado.
7. No fim, parar transmissao no OBS.
8. Se houver replay, editar o evento para `Replay`.
