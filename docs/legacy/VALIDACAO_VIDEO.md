# Validação — 20/10/2026

- Dependências de execução instaladas em `.venv`; `pip check`: nenhum requisito quebrado.
- Original: importação, leitura da foto e geração de quadro ASCII executadas com sucesso. Alterações de qualidade e comportamento descritas no README.
- Os três arquivos em `original/` são idênticos byte a byte aos arquivos do ZIP.
- SHA-256 da foto original e de `assets/irina.jpg`: `96869dbd64c6bbee9cd56de4c487cc3c5e20423110b0f5065602838915bf288a`.
- Cinco testes automatizados passaram: formato padrão, grade fina, erro de foto ausente, determinismo e continuidade das posições nas fronteiras das fases.
- Prévia: 540 × 960, 30 FPS, 480 quadros; decodificação integral sem erros; nenhum quadro preto.
- Final: H.264, `yuv420p`, 1080 × 1920, 30/1 FPS, 480 quadros, 16 segundos, 37.663.569 bytes. Decodificação integral pelo FFmpeg concluída sem erros.
- Inspeção visual: quadros da prévia nas fases de retrato, piscada, olho, coração, transformação e dragão; detalhe do rosto em resolução final; retrato e dragão extraídos do MP4 final.
- A otimização de grade bidimensional para `--cell 5` preserva os pixels da configuração padrão em cinco tempos amostrados.

Os testes de continuidade verificam posições imediatamente antes e depois das fronteiras; não constituem uma avaliação automática da estética. A fidelidade está limitada à fotografia fornecida (uma captura de tela de 707 × 1536); o zoom amplia esses detalhes sem geração de um novo rosto.

A execução é determinística no mesmo ambiente. Fontes e versões de bibliotecas diferentes podem alterar o raster dos caracteres. Não foi adicionada trilha sonora.
