# Validação da execução ao vivo

20/10/2026, macOS Intel, Python 3.9.6, Pygame-ce 2.5.6.

- `main.py` agora inicia uma janela Pygame. Não lê nem gera vídeo.
- Dependências: `pip check` sem requisitos quebrados.
- Quinze testes passaram. Além da construção progressiva, continuidade, determinismo, piscada e controles, foram verificados a separação entre tons claros, a densidade mínima do retrato, a calibração da luminosidade real dos caracteres e a equivalência do desenho individual com o desenho da grade otimizada.
- Teste de desenho: 180 quadros amostrados ao longo das fases, 1280 × 720, 19.170 caracteres principais, 87,8 quadros/s em memória. Não inclui a apresentação no monitor.
- Janela nativa executada por 23,01 segundos: 1.313 quadros, média de 57,1 quadros/s, com limite configurado de 60. A sequência completa de 22 segundos foi executada.
- Eventos Pygame de pausa, reinício, seleção da cena do olho, velocidade e ocultação da interface foram enviados e processados pela mesma função usada na janela.
- Comparações antes/depois foram criadas para retrato, rosto e olho em `output/quality/`.
- Dez capturas do próprio renderizador foram inspecionadas para formação do retrato, piscada, rosto, olho, transformação, coração e dragão. O título usa a transparência real da fonte para formar suas letras, sem um retângulo preenchido.
- `py_compile`, `git diff --check` e análise de sintaxe do iniciador zsh concluídos sem erros.
- A foto continua com SHA-256 `96869dbd64c6bbee9cd56de4c487cc3c5e20423110b0f5065602838915bf288a`.

A velocidade medida se refere a esta máquina e pode variar com o hardware, o tamanho da janela e a densidade. O teste automatizado não substitui a avaliação estética do usuário. Tela cheia, redimensionamento e clique na barra estão implementados; não foram confirmados manualmente em todos os sistemas. O programa foi executado em macOS; Windows e Linux não foram executados nesta sessão.

O código anterior de exportação permanece separado como histórico. Nenhum novo MP4 foi criado nesta etapa.

A revisão de qualidade remove a saturação precoce dos tons claros, reduz o brilho externo e escolhe o formato das letras por densidade de tinta medida. A resposta tonal calibrada foi testada com erro médio inferior a 2% em todas as paletas, sem desenhar pixels da fotografia na janela. A preservação de fidelidade é uma avaliação visual; esse teste tonal não é uma métrica de reconhecimento de identidade.

Na revisão de organização do código, os estados das partículas e os pixels de onze quadros representativos foram comparados antes e depois: permaneceram idênticos byte a byte. Ruff verificou imports e formatação; a máscara arredondada do chapéu também está coberta por um teste de regressão.
