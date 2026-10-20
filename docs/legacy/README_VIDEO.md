# Irina → Olho → Coração → Kali Linux

Animação Python determinística, vertical, 16 segundos, 30 FPS. A fotografia fornece as cores e a forma do rosto; todos os elementos visíveis são caracteres ASCII, partículas e o brilho calculado a partir deles. Não há cortes entre imagens. Sem áudio.

## Arquivos

- `original/`: os três arquivos extraídos do ZIP, intactos.
- `assets/irina.jpg`: cópia idêntica da foto original.
- `assets/kali-dragon.png`: máscara transparente do dragão oficial.
- `main.py`: renderizador atualizado.
- `test_animation.py`: validação de continuidade, determinismo e configuração.
- `output/preview.mp4`: prévia em 540 × 960, 30 FPS.
- `output/irina_kali_1080x1920.mp4`: entrega final H.264, 1080 × 1920, 30 FPS.
- `output/*.json`: parâmetros e SHA-256 da foto usada.

## Instalação

Use Python 3.9–3.12 e FFmpeg disponível no PATH. As versões fixadas foram executadas com Python 3.9.6 e FFmpeg 9.0.1, macOS Intel.

```bash
cd irina-ascii
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
ffmpeg -version
```

Para instalar FFmpeg no macOS com Homebrew: `brew install ffmpeg`. No Ubuntu/Debian: `sudo apt install ffmpeg fonts-dejavu-core`. No Windows, instale FFmpeg e adicione sua pasta `bin` ao PATH. O renderizador procura Menlo, DejaVu Sans Mono ou Consolas; se nenhuma existir, usa a fonte interna do Pillow. A fonte pode alterar ligeiramente a textura entre sistemas.

## Executar

```bash
# Testes rápidos
.venv/bin/python -m unittest -v

# Prévia completa, mesmas trajetórias da versão final
.venv/bin/python main.py --preview

# Quadros para inspeção visual
.venv/bin/python main.py --preview --stills

# MP4 final, 1080 × 1920, 30 FPS
.venv/bin/python main.py

# Verificação técnica e decodificação integral
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames,pix_fmt -show_entries format=duration -of json output/irina_kali_1080x1920.mp4
ffmpeg -v error -i output/irina_kali_1080x1920.mp4 -f null -
```

A gravação usa um arquivo `.partial.mp4`; somente após FFmpeg concluir ele recebe o nome final. O progresso aparece a cada segundo do vídeo. O render é feito em CPU e pode levar vários minutos.

## Personalizar

```bash
# Outro destino
.venv/bin/python main.py --output output/minha_animacao.mp4

# ASCII mais fino: mais caracteres, processamento maior
.venv/bin/python main.py --cell 5

# ASCII maior e mais evidente
.venv/bin/python main.py --cell 10

# Variação reprodutível das trajetórias
.venv/bin/python main.py --seed 17

# Outra máscara transparente (PNG RGBA)
.venv/bin/python main.py --logo assets/meu_logo.png

# Outro tamanho vertical
.venv/bin/python main.py --width 720 --height 1280 --fps 30
```

`--duration` limita ou prolonga a gravação; não reescala os tempos das fases. Para conservar a sequência completa, use pelo menos 16 segundos. `--photo` aceita outro arquivo, mas as coordenadas dos olhos, o enquadramento e a piscada foram calibrados especificamente para a foto anexada. Para outra foto, ajuste `Scene.eye`, `Scene.camera()` e as duas elipses de `Scene.portrait()`. A imagem é normalizada para 707 × 1536 apenas em memória.

Ajuste cores em `heart_color` e `dragon_color`; a paleta do retrato vem dos pixels originais com elevação de luminosidade. Ajuste o batimento em `state()`, a densidade com `--cell` e a amplitude das trajetórias nos termos `arc`. As posições usam coordenadas de projeto 1080 × 1920 e são escaladas na saída.

## Roteiro e transições

| Tempo | Ação |
|---|---|
| 0–3 s | Retrato ASCII; piscada elíptica centrada em 2,35 s |
| 3–6 s | Zoom exponencial contínuo até o olho à esquerda da imagem |
| 6–8 s | Partículas do olho viajam por curvas e formam o coração |
| 8–10,5 s | Coração pulsa; velocidades chegam suavemente a zero nos extremos |
| 10,5–14,5 s | As mesmas partículas se reorganizam no dragão; vermelho passa por violeta até azul |
| 14,5–16 s | Símbolo formado e título desenhado com caracteres |

As curvas usam *smootherstep* de quinta ordem. Cada partícula tem identidade estável; sua posição é calculada pelo tempo, sem depender do quadro anterior. A associação espacial Morton aproxima vizinhanças entre as formas. O espalhamento intermediário faz parte da transformação; não se trata de dissolver duas imagens estáticas. O zoom amostra exclusivamente a foto original: não inventa detalhes além da resolução de origem.

## Análise e correções

O original não apresentava erro de sintaxe. Os problemas principais eram de comportamento e entrega:

- Saída em 24 FPS, diferente dos 30 FPS solicitados.
- Olhos estimados em `0,37 × altura`, incompatíveis com esta foto.
- Piscada representada por retângulo escuro; substituída por máscaras elípticas com amostragem da pele e linha das pálpebras.
- Mudança descontínua de câmera e corte olho → coração. A câmera agora tem um único movimento contínuo; o coração recebe as partículas que já compõem o olho.
- Coração → dragão era uma dissolução de máscaras. Agora há correspondência de partículas com trajetórias curvas durante quatro segundos.
- Sementes mudavam a cada poucos quadros, provocando cintilação. Agora a aleatoriedade é fixa e as partículas se movem continuamente.
- O ZIP não incluía logo. O desenho aproximado foi substituído pela máscara do símbolo oficial, convertida em ASCII durante o render.
- `mp4v` foi substituído por H.264 com `yuv420p` e `faststart` para reprodução ampla.
- Enquadramento da foto exclui os elementos da interface do celular; o JPEG original permanece intacto.
- Fontes e atlas são carregados uma vez, em lugar de redesenhados caractere por caractere a cada quadro.
- A grade de amostragem é bidimensional para evitar o limite de 32.767 linhas de `cv2.remap` ao selecionar ASCII mais fino (`--cell 5`).

## Origem dos materiais

Fotografia: arquivo fornecido pelo usuário, preservado sem retoque generativo.

Dragão: [Kali Linux Press Pack — Logomark](https://gitlab.com/kalilinux/documentation/press-pack/-/tree/main/Kali/Logomark), arquivo `kali-dragon-white-transparent.png`, obtido em 20/10/2026. A máscara preserva o desenho do símbolo; a animação atribui a cor azul. As marcas pertencem aos respectivos titulares.
