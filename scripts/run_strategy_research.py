"""Download several years of Binance Spot candles and write an auditable report."""

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "trader"))

from src.backtest import BacktestConfig, run_backtest, run_backtest_splits, run_parameter_sweep, run_walk_forward
from src.binance import BinancePublicClient
from src.research_quality import inspect_candles, sample_quality


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def main() -> None:
    # Three years gives materially more context than the original 499 candles.
    end = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    start = int((datetime.now(tz=timezone.utc).replace(year=datetime.now(tz=timezone.utc).year - 3)).timestamp() * 1000)
    client = BinancePublicClient()
    print("Baixando BTCUSDT 1h da Binance Spot...")
    candles = client.klines_history("BTCUSDT", "1h", start_time=start, end_time=end)
    if len(candles) < 200:
        raise RuntimeError(f"histórico insuficiente: {len(candles)} candles")
    quality = inspect_candles(candles, 3_600_000)
    config = BacktestConfig(fast_period=20, slow_period=50, atr_period=14)
    baseline, trades = run_backtest(candles, config)
    splits = run_backtest_splits(candles, config)
    sweep = run_parameter_sweep(candles, config)
    walk = run_walk_forward(candles, config, folds=4)
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    lines = [
        "# Pesquisa de Estratégia — EMA Trend",
        "",
        f"Gerado em: {datetime.now(tz=timezone.utc).isoformat()}",
        "Fonte: Binance Spot pública, candles fechados BTCUSDT/1h.",
        "",
        "## Qualidade dos dados",
        f"- Período: {iso(candles[0].open_time)} → {iso(candles[-1].open_time)}",
        f"- Candles: {quality.candles}",
        f"- Duplicados: {quality.duplicates}",
        f"- OHLC inválido: {quality.invalid_ohlc}",
        f"- Volume negativo: {quality.negative_volume}",
        f"- Fora de ordem: {quality.non_monotonic}",
        f"- Gaps: {quality.gaps}",
        f"- Qualidade: {'PASS' if quality.valid else 'FAIL'}",
        "",
        "## Baseline sem otimização",
        "Parâmetros: EMA 20 / EMA 50, ATR 14, capital inicial $10.000, taxa 10 bps, slippage 5 bps.",
        "",
        f"- Retorno: {baseline.return_percent:.2f}%",
        f"- Buy & Hold: {baseline.buy_hold_return_percent:.2f}%",
        f"- Excesso sobre Buy & Hold: {baseline.return_percent - baseline.buy_hold_return_percent:.2f} p.p.",
        f"- CAGR: {baseline.cagr_percent:.2f}%",
        f"- Drawdown máximo: {baseline.max_drawdown_percent:.2f}%",
        f"- Sharpe / Sortino: {baseline.sharpe:.2f} / {baseline.sortino:.2f}",
        f"- Profit factor / expectativa: {baseline.profit_factor if baseline.profit_factor is not None else '—'} / {baseline.expectancy:.2f}",
        f"- Win rate: {baseline.win_rate_percent:.2f}%",
        f"- Trades: {len(trades)} ({sample_quality(len(trades))})",
        f"- Taxas / slippage / spread: ${baseline.fees:.2f} / ${baseline.slippage:.2f} / ${baseline.spread:.2f}",
        f"- Exposição: {baseline.exposure_percent:.2f}% do tempo",
        "",
        "## Divisão cronológica",
    ]
    for split in splits:
        lines.append(f"- {split['name']}: {iso(split['data_start'])} → {iso(split['data_end'])}; retorno {split['metrics']['return_percent']:.2f}%; trades {split['trades']}")
    lines += ["", "## Robustez de parâmetros (pesquisa, não escolha automática)", "", "| EMA rápida | EMA lenta | Retorno | Trades |", "|---:|---:|---:|---:|"]
    for row in sweep:
        lines.append(f"| {row['fast_period']} | {row['slow_period']} | {row['metrics']['return_percent']:.2f}% | {row['metrics']['trades']} |")
    lines += ["", "## Walk-forward", f"- Folds calculados: {len(walk.get('folds', []))}", "- Seleção feita somente na validação; OOS permanece intocado.", ""]
    for fold in walk.get("folds", []):
        oos = fold["out_of_sample"]
        lines.append(f"- Fold {fold['fold']}: EMA {fold['selected']['fast_period']}/{fold['selected']['slow_period']}; OOS {oos['metrics']['return_percent']:.2f}%; trades {oos['metrics']['trades']}")
    lines += ["", "## Conclusão", "", "Classificação: INCONCLUSIVA.", "", "O baseline e o OOS devem ser avaliados com mais trades antes de qualquer decisão. Resultado positivo isolado não prova edge; amostras pequenas são apenas alerta de tamanho e não evidência de lucratividade.", "", "Monte Carlo e regimes bull/bear/lateral ficam condicionados a uma amostra de trades maior que a atual."]
    (reports / "STRATEGY_RESEARCH.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Relatório criado: {reports / 'STRATEGY_RESEARCH.md'}")
    print(f"Candles: {len(candles)} | Trades: {len(trades)} | Qualidade: {'PASS' if quality.valid else 'FAIL'}")


if __name__ == "__main__":
    main()
