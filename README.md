# CLK — Indicadores de prospecção

Site estático público com indicadores agregados da operação de prospecção da CLK: contagens por nota, etapa e lote, além de gráficos de evolução diária e semanal.

Este repositório contém apenas números agregados. Não há nomes de marcas, pessoas, perfis, mensagens, dossiês nem dados comerciais individuais.

A página é publicada no GitHub Pages a partir de `index.html`. O script `build_publico.py` regenera esse arquivo a partir dos manifestos e fichas de um repositório privado de entregas, usando um caminho configurável (`--repo`, padrão `/workspace/clk-git/repo`).

```bash
python3 build_publico.py --repo /caminho/do/repositorio-privado --out .
```
