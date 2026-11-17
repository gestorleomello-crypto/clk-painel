#!/usr/bin/env python3
"""Regenera o site público de indicadores agregados a partir do repositório de entregas.

Não inclui nomes de marca, pessoas, @, sites de loja nem mensagens.
Uso: python3 build_publico.py [--repo CAMINHO] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
PILOTO_LOTE = "L2026-11-13-01"
ETAPAS_COMERCIAIS = (
    "PESQUISADA",
    "VALIDADA",
    "PRONTA",
    "CONTATADA",
    "RESPONDEU",
    "REUNIÃO",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gera index.html público só com indicadores agregados.")
    p.add_argument("--repo", default="/workspace/clk-git/repo", help="Caminho do repositório local")
    p.add_argument("--out", default=str(Path(__file__).resolve().parent), help="Pasta de saída")
    p.add_argument("--data", default="", help="data.json da central (só contagens agregadas entram no HTML)")
    return p.parse_args()


def carregar(repo: Path) -> dict:
    entregas = repo / "entregas"
    if not entregas.is_dir():
        raise SystemExit(f"Pasta de entregas não encontrada: {entregas}")

    lotes = []
    notas = Counter()
    fichas_comerciais = 0
    descartes = 0
    diario = {}  # YYYY-MM-DD -> {fichas, descartes}

    for pasta in sorted(entregas.iterdir()):
        man_path = pasta / "MANIFESTO.json"
        if not man_path.is_file():
            continue
        man = json.loads(man_path.read_text())
        lote_id = man.get("lote_id") or pasta.name
        n_fichas = len(man.get("empresas") or [])
        n_descartes = len(man.get("descartes") or [])
        entregue = man.get("entregue_em") or ""
        piloto = lote_id == PILOTO_LOTE

        # data da entrega no fuso de Brasília
        data_iso = "NÃO VERIFICADO"
        if entregue:
            try:
                dt = datetime.fromisoformat(entregue)
                data_iso = dt.astimezone(TZ).date().isoformat()
            except ValueError:
                data_iso = entregue[:10] if len(entregue) >= 10 else "NÃO VERIFICADO"

        lotes.append({
            "lote": lote_id,
            "pedido": man.get("pedido_id") or "NÃO VERIFICADO",
            "data": data_iso,
            "fichas": n_fichas,
            "descartes": n_descartes,
            "piloto": piloto,
        })

        if piloto:
            continue

        fichas_comerciais += n_fichas
        descartes += n_descartes
        if data_iso not in diario:
            diario[data_iso] = {"fichas": 0, "descartes": 0}
        diario[data_iso]["fichas"] += n_fichas
        diario[data_iso]["descartes"] += n_descartes

        fichas_dir = pasta / "fichas"
        if fichas_dir.is_dir():
            for fp in fichas_dir.glob("*.json"):
                ficha = json.loads(fp.read_text())
                grade = ((ficha.get("prospecting") or {}).get("icp_grade")) or "NÃO VERIFICADO"
                notas[grade] += 1

    etapas = {nome: 0 for nome in ETAPAS_COMERCIAIS}
    etapas["PESQUISADA"] = fichas_comerciais
    etapas["DESCARTADA"] = descartes
    etapas["PENDENTE"] = 0
    etapas["NÃO CONTATAR"] = 0

    # semanas (segunda a domingo) a partir das datas diárias
    semanal = {}
    for data, vals in diario.items():
        if data == "NÃO VERIFICADO":
            chave = "NÃO VERIFICADO"
        else:
            d = datetime.fromisoformat(data).date()
            segunda = d.fromordinal(d.toordinal() - d.weekday())
            domingo = d.fromordinal(segunda.toordinal() + 6)
            chave = f"{segunda.strftime('%d/%m')}–{domingo.strftime('%d/%m/%Y')}"
        semanal.setdefault(chave, {"fichas": 0, "descartes": 0})
        semanal[chave]["fichas"] += vals["fichas"]
        semanal[chave]["descartes"] += vals["descartes"]

    agora = datetime.now(TZ)
    return {
        "atualizado_em": agora.strftime("%d/%m/%Y, %H:%M"),
        "fichas_comerciais": fichas_comerciais,
        "descartes": descartes,
        "notas": dict(notas),
        "etapas": etapas,
        "lotes": lotes,
        "diario": diario,
        "semanal": semanal,
    }


def fmt_data(iso: str) -> str:
    if not iso or iso == "NÃO VERIFICADO" or len(iso) < 10:
        return "NÃO VERIFICADO"
    y, m, d = iso.split("-")[:3]
    return f"{d}/{m}/{y}"


def barra(valor: int, teto: int, cor: str) -> str:
    largura = 0 if teto <= 0 or valor <= 0 else max(4, int(round(100 * valor / teto)))
    return (
        f'<div class="bar-row"><span class="bar-track">'
        f'<span class="bar-fill" style="width:{largura}%;background:{cor}"></span>'
        f'</span><span class="bar-val">{valor}</span></div>'
    )


def render(data: dict) -> str:
    notas = data["notas"]
    etapas = data["etapas"]
    diario = data["diario"]
    semanal = data["semanal"]
    teto_dia = max([0] + [v["fichas"] + v["descartes"] for v in diario.values()])
    teto_sem = max([0] + [v["fichas"] + v["descartes"] for v in semanal.values()])

    notas_html = "".join(
        f'<div class="stat"><strong>{notas.get(letra, 0)}</strong><span>Nota {letra}</span></div>'
        for letra in ("A", "B", "C")
    )

    etapas_rows = ""
    for nome in list(ETAPAS_COMERCIAIS) + ["DESCARTADA", "PENDENTE", "NÃO CONTATAR"]:
        etapas_rows += f"<tr><th>{nome}</th><td>{etapas.get(nome, 0)}</td></tr>"

    lote_rows = ""
    for lote in data["lotes"]:
        if lote["piloto"]:
            obs = "Lote de teste — excluído dos indicadores"
        else:
            obs = "Entrega comercial"
        lote_rows += (
            f"<tr><td>{lote['lote']}</td><td>{lote['pedido']}</td>"
            f"<td>{fmt_data(lote['data'])}</td><td>{lote['fichas']}</td>"
            f"<td>{lote['descartes']}</td><td>{obs}</td></tr>"
        )

    diario_html = ""
    for dia in sorted(diario):
        vals = diario[dia]
        diario_html += (
            f'<div class="chart-item"><div class="chart-label">{fmt_data(dia)}</div>'
            f'<div class="chart-pair">{barra(vals["fichas"], teto_dia, "#102117")}'
            f'{barra(vals["descartes"], teto_dia, "#DDC1A1")}</div>'
            f'<div class="chart-meta">Fichas {vals["fichas"]} · Descartes {vals["descartes"]}</div></div>'
        )

    semanal_html = ""
    for semana, vals in semanal.items():
        semanal_html += (
            f'<div class="chart-item"><div class="chart-label">{semana}</div>'
            f'<div class="chart-pair">{barra(vals["fichas"], teto_sem, "#102117")}'
            f'{barra(vals["descartes"], teto_sem, "#DDC1A1")}</div>'
            f'<div class="chart-meta">Fichas {vals["fichas"]} · Descartes {vals["descartes"]}</div></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CLK — Indicadores de prospecção</title>
  <style>
    :root {{
      --verde: #102117;
      --branco: #F8F8F8;
      --preto: #000000;
      --bege: #DDC1A1;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--branco);
      color: var(--preto);
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      line-height: 1.45;
    }}
    header {{
      background: var(--verde);
      color: var(--branco);
      padding: 28px 20px 24px;
      border-bottom: 4px solid var(--bege);
    }}
    header .kicker {{
      letter-spacing: 0.14em;
      font-size: 11px;
      text-transform: uppercase;
      color: var(--bege);
      margin: 0 0 8px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; font-weight: 600; }}
    header p {{ margin: 0; font-size: 14px; opacity: 0.9; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 24px 20px 64px; }}
    h2 {{ font-size: 18px; margin: 32px 0 12px; color: var(--verde); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }}
    @media (min-width: 800px) {{
      .grid {{ grid-template-columns: repeat(6, 1fr); }}
    }}
    .stat, .card {{
      background: #fff;
      border: 1px solid var(--bege);
      border-radius: 8px;
      padding: 16px;
    }}
    .stat strong {{ display: block; font-size: 28px; color: var(--verde); }}
    .stat span {{ font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border: 1px solid var(--bege);
      font-size: 14px;
    }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #eee; }}
    th {{ color: var(--verde); font-weight: 600; }}
    .charts {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 20px;
    }}
    @media (min-width: 800px) {{
      .charts {{ grid-template-columns: 1fr 1fr; }}
    }}
    .bar-row {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; }}
    .bar-track {{
      flex: 1;
      height: 10px;
      background: #eee;
      border-radius: 99px;
      overflow: hidden;
    }}
    .bar-fill {{ display: block; height: 100%; border-radius: 99px; }}
    .bar-val {{ width: 2em; text-align: right; font-size: 12px; }}
    .chart-item {{ margin-bottom: 14px; }}
    .chart-label {{ font-size: 13px; font-weight: 600; color: var(--verde); }}
    .chart-meta {{ font-size: 12px; color: #444; }}
    .legend {{ font-size: 12px; margin-bottom: 8px; }}
    .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 99px; margin-right: 4px; }}
    footer {{
      margin-top: 40px;
      font-size: 12px;
      color: #444;
    }}
  </style>
</head>
<body>
  <header>
    <p class="kicker">CLK · Prospecção</p>
    <h1>Indicadores agregados</h1>
    <p>Atualizado em {data["atualizado_em"]} (horário de Brasília). Visualização pública, sem dados individuais.</p>
  </header>
  <main>
    <h2>Pipeline</h2>
    <div class="grid">
      <div class="stat"><strong>{etapas["PESQUISADA"]}</strong><span>Pesquisadas</span></div>
      <div class="stat"><strong>{etapas["VALIDADA"]}</strong><span>Validadas</span></div>
      <div class="stat"><strong>{etapas["PRONTA"]}</strong><span>Prontas</span></div>
      <div class="stat"><strong>{etapas["CONTATADA"]}</strong><span>Contatadas</span></div>
      <div class="stat"><strong>{etapas["RESPONDEU"]}</strong><span>Respostas</span></div>
      <div class="stat"><strong>{etapas["REUNIÃO"]}</strong><span>Reuniões</span></div>
    </div>

    <h2>Notas e descartes</h2>
    <div class="grid">
      {notas_html}
      <div class="stat"><strong>{data["descartes"]}</strong><span>Descartadas</span></div>
    </div>

    <h2>Contatos e follow-ups (agregados)</h2>
    <p style="font-size:13px;margin:0 0 12px">Só contagens. Sem nomes, perfis ou mensagens. Ausência de fonte não é omitida: quando o arquivo de registros existe e está vazio, o valor é zero real.</p>
    <div class="grid">
      <div class="stat"><strong>{(data.get("contatos") or {}).get("validadas", data["etapas"].get("VALIDADA", 0))}</strong><span>Validadas</span></div>
      <div class="stat"><strong>{(data.get("contatos") or {}).get("prontas", data["etapas"].get("PRONTA", 0))}</strong><span>Prontas</span></div>
      <div class="stat"><strong>{(data.get("contatos") or {}).get("contatadas", 0)}</strong><span>Contatadas</span></div>
      <div class="stat"><strong>{(data.get("contatos") or {}).get("respostas", 0)}</strong><span>Respostas</span></div>
      <div class="stat"><strong>{(data.get("contatos") or {}).get("followups_abertos", 0)}</strong><span>Follow-ups abertos</span></div>
      <div class="stat"><strong>{(data.get("contatos") or {}).get("reunioes", 0)}</strong><span>Reuniões</span></div>
    </div>

    <h2>Evolução</h2>
    <div class="legend">
      <span class="dot" style="background:#102117"></span> Fichas
      <span class="dot" style="background:#DDC1A1;margin-left:12px"></span> Descartes
    </div>
    <div class="charts">
      <section class="card">
        <h2 style="margin-top:0">Por dia de entrega</h2>
        {diario_html or "<p>NÃO VERIFICADO</p>"}
      </section>
      <section class="card">
        <h2 style="margin-top:0">Por semana</h2>
        {semanal_html or "<p>NÃO VERIFICADO</p>"}
      </section>
    </div>

    <h2>Por lote</h2>
    <table>
      <thead>
        <tr><th>Lote</th><th>Pedido</th><th>Data</th><th>Fichas</th><th>Descartes</th><th>Observação</th></tr>
      </thead>
      <tbody>
        {lote_rows}
      </tbody>
    </table>

    <h2>Etapas</h2>
    <table>
      <thead><tr><th>Etapa</th><th>Quantidade</th></tr></thead>
      <tbody>{etapas_rows}</tbody>
    </table>

    <footer>
      Fonte: manifestos e fichas do repositório de entregas. A ficha do lote de teste não entra nos indicadores.
      Nenhuma etapa além de PESQUISADA e DESCARTADA foi atribuída automaticamente. Faturamento e performance interna não são publicados aqui.
    </footer>
  </main>
</body>
</html>
"""


def aplicar_agregados(base: dict, data_path: Path) -> dict:
    """Incorpora só contagens de etapa, contato e follow-up. Ignora qualquer nome."""
    bruto = json.loads(data_path.read_text(encoding="utf-8"))
    ind = bruto.get("indicadores") or {}
    etapas = {nome: 0 for nome in list(ETAPAS_COMERCIAIS) + ["DESCARTADA", "PENDENTE", "NÃO CONTATAR", "PRONTA PARA ABORDAGEM"]}
    for marca in bruto.get("marcas") or []:
        # use only the etapa field; never copy names
        etapa = marca.get("etapa") if isinstance(marca, dict) else None
        if etapa:
            etapas[etapa] = etapas.get(etapa, 0) + 1
    # map PRONTA PARA ABORDAGEM onto prontas display
    if "PRONTA PARA ABORDAGEM" in etapas:
        etapas["PRONTA"] = etapas.get("PRONTA", 0) + etapas["PRONTA PARA ABORDAGEM"]
    base["etapas"] = etapas
    def num(chave: str, default: int = 0) -> int:
        item = ind.get(chave) or {}
        valor = item.get("valor")
        return default if valor is None else int(valor)
    base["contatos"] = {
        "contatadas": num("contatadas"),
        "respostas": num("respostas"),
        "followups_abertos": num("followups_abertos"),
        "reunioes": num("reunioes"),
        "prontas": num("prontas"),
        "validadas": num("validadas"),
    }
    if "atualizado_em" in bruto and bruto["atualizado_em"]:
        # data.json uses gerado_em already formatted
        pass
    if bruto.get("gerado_em"):
        base["atualizado_em"] = bruto["gerado_em"]
    return base


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    dados = carregar(repo)
    if args.data:
        dp = Path(args.data)
        if not dp.is_file():
            raise SystemExit(f"data.json não encontrado: {dp}")
        dados = aplicar_agregados(dados, dp)
    html = render(dados)
    destino = out / "index.html"
    destino.write_text(html, encoding="utf-8")
    print(f"Gerado {destino}")


if __name__ == "__main__":
    main()
