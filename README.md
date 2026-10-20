# Irina ASCII

**Irina → olho → coração → Kali Linux, em tempo real.**

![Retrato reconstruído com caracteres ASCII](docs/images/irina-ascii.png)

Programa Python que abre uma janela horizontal e reconstrói a Irina com caracteres, letra por letra. Depois anima a piscada, aproxima o rosto e o olho e reorganiza os caracteres em coração e dragão do Kali. A imagem é calculada durante a execução; não há reprodução ou geração de vídeo no comando principal.

## Abrir no macOS

Dê duplo clique em **Iniciar Irina.command**. Na primeira execução, o iniciador cria `.venv` e instala as dependências, se necessário. Requer Python 3.9–3.12.

Ou execute pelo Terminal, na pasta do projeto:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

A janela padrão tem 1280 × 720, uma grade de 213 × 90 caracteres e limite de 60 atualizações por segundo. Pode ser redimensionada; a imagem mantém sua proporção e recebe margens pretas. A sequência dura 22 segundos e repete. Use `--once` para pausar no último desenho.

## Controles

| Tecla | Ação |
|---|---|
| Espaço | Pausar / continuar |
| R | Reconstruir desde a primeira letra |
| ← / → | Voltar / avançar um segundo |
| 1 / 2 / 3 / 4 / 5 | Retrato / rosto / olho / coração / Kali |
| + / − | Velocidade de 0,25× a 2× |
| F | Tela cheia / janela |
| H | Mostrar / ocultar controles |
| Esc | Sair |
| Clique na barra inferior | Ir para um instante da animação |

## Personalizar

```bash
# Letras maiores, parecidas com uma grade de terminal
.venv/bin/python main.py --cell 14

# Padrão com maior detalhe no rosto
.venv/bin/python main.py --cell 6

# Equilíbrio entre detalhe e letras maiores
.venv/bin/python main.py --cell 8

# Janela menor e limite de 30 FPS, para computadores mais lentos
.venv/bin/python main.py --width 960 --height 540 --fps 30

# Começar pelo olho e pausar na última cena
.venv/bin/python main.py --start 8.5 --once

# Repetir com outra distribuição de caracteres
.venv/bin/python main.py --seed 17
```

O limite de FPS é uma meta de atualização, não uma promessa de desempenho em qualquer computador. A animação usa segundos reais; computadores mais lentos mantêm a duração da sequência. A formação inicial é uma onda de revelação de letras com deslocamento e luminosidade próprios; não é uma digitação serial de um único caractere por vez.

## Qualidade do desenho

O padrão `--cell 6` usa 19.170 caracteres principais, com letras finas o suficiente para manter os detalhes do rosto. A iluminação original recebe apenas contraste local moderado e nitidez leve, sem saturar as áreas claras do rosto e do chapéu.

Cada letra é medida pela quantidade real de tinta que ocupa na célula. O renderizador escolhe formas com densidade adequada e calibra sua luminosidade para reproduzir o tom da fotografia. A variedade das letras continua determinística, mas deixa de criar manchas aleatórias no rosto. A fonte cabe em sua própria célula, e o brilho externo foi reduzido para manter os detalhes dos olhos, nariz e lábios.

Na fase de retrato já montado, as mesmas letras em cache são organizadas em uma grade NumPy. Durante a construção e as transformações, elas continuam sendo partículas individuais. Essa otimização mantém os dois caminhos visualmente equivalentes.

## Como funciona

- `main.py` inicia a janela. Não usa FFmpeg nem abre MP4.
- `ascii_engine.py` calcula posições, caracteres, luminosidade, câmera, piscada e correspondências entre formas. É possível consultar qualquer instante diretamente.
- `live_app.py` desenha os caracteres em Pygame usando um atlas de letras coloridas em cache, trata teclado, pausa, redimensionamento e velocidade.
- `assets/irina.jpg` é a fotografia original, idêntica à fornecida. A foto serve de referência de luminosidade e geometria. Seus pixels não são desenhados na janela.
- `assets/references/` guarda as quatro referências de estilo recebidas. Elas não são usadas como quadros prontos.
- `assets/kali-dragon.png` fornece a máscara do símbolo oficial, também reconstruída em caracteres.

A paleta de cobre, laranja, creme e vermelho segue as referências. Ela chega gradualmente ao azul no Kali. O fundo tem rastros horizontais de código e brilhos de caracteres `+`. O recorte da silhueta remove o ambiente e a interface do celular apenas durante a amostragem; o arquivo da foto fica intacto.

O mesmo conjunto de partículas liga olho, coração e dragão por trajetórias curvas. Durante a compactação, caracteres excedentes perdem luminosidade para que as formas continuem legíveis. Não há cortes entre capturas de tela. A piscada modifica localmente a amostragem dos olhos com pele vizinha; não é uma fotografia adicional.

## Alterar o código

Em `ascii_engine.py`, ajuste:

- `CHARS`: conjunto de letras, números e símbolos.
- `Animation.birth` e `spawn`: ordem e movimento da construção letra por letra.
- `Animation.camera()`: enquadramento e aproximação contínua.
- `Animation.portrait()`: luminosidade e máscaras das pálpebras.
- `Animation.make_shape()`: coração e máscara do dragão.
- `Animation.state()`: tempos, trajetórias e batimento.

Em `live_app.py`, `Renderer` contém a paleta, o tamanho das letras, os rastros e o brilho. Não recalcula fontes a cada quadro.

A calibração do rosto e da silhueta é específica à foto fornecida, normalizada em memória para 707 × 1536. `--photo` aceita outro arquivo, mas outra pessoa ou outro enquadramento exige atualizar as coordenadas. O zoom respeita o detalhe existente; não inventa um novo rosto.

## Verificar

```bash
.venv/bin/python -m pip check
.venv/bin/python -m unittest test_realtime test_renderer_quality -v

# Desenha todas as fases, mede velocidade e testa eventos de teclado.
# Não abre janela e não produz vídeo.
.venv/bin/python main.py --check
```

A verificação salva imagens e um relatório em `output/live_checks/`. O resultado de velocidade mede o desenho em memória; não inclui sincronização com o monitor ou apresentação da janela.

A fonte preferida é Menlo no macOS, DejaVu Sans Mono no Linux e Consolas no Windows; há uma fonte interna como alternativa. A aparência pode variar entre sistemas.

## Materiais e referências

A referência original fica em `original/`. O exportador opcional está em `render_video.py`, com documentação em `docs/legacy/`; a execução ao vivo usa apenas `main.py`.

O dragão vem do [Kali Linux Press Pack oficial](https://gitlab.com/kalilinux/documentation/press-pack/-/tree/main/Kali/Logomark). A renderização em lote de letras usa [`Surface.blits` do Pygame](https://pyga.me/docs/ref/surface.html#pygame.Surface.blits). As marcas pertencem aos seus titulares.

## Desenvolvimento

Os comentários e as funções estão organizados por responsabilidade: simulação, preparação das letras, desenho e controles. Para conferir formatação e testes:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m unittest -v
```

A foto e as referências visuais fazem parte deste projeto. Publicar o código não transfere direitos sobre a imagem da pessoa fotografada nem sobre as marcas utilizadas.
