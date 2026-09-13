# Pesquisa de Estratégia — EMA Trend

Gerado em: 2026-09-13T10:08:26.475830+00:00
Fonte: Binance Spot pública, candles fechados BTCUSDT/1h.

## Qualidade dos dados
- Período: 2023-09-13 → 2026-09-13
- Candles: 26304
- Duplicados: 0
- OHLC inválido: 0
- Volume negativo: 0
- Fora de ordem: 0
- Gaps: 0
- Qualidade: PASS

## Baseline sem otimização
Parâmetros: EMA 20 / EMA 50, ATR 14, capital inicial $10.000, taxa 10 bps, slippage 5 bps.

- Retorno: 1.91%
- Buy & Hold: 193.07%
- Excesso sobre Buy & Hold: -191.17 p.p.
- CAGR: 0.03%
- Drawdown máximo: 7.98%
- Sharpe / Sortino: 0.04 / 0.06
- Profit factor / expectativa: 1.0639211133636182 / 0.78
- Win rate: 29.10%
- Trades: 244 (MODERATE SAMPLE)
- Taxas / slippage / spread: $505.76 / $252.88 / $0.00
- Exposição: 53.70% do tempo

## Divisão cronológica
- in_sample: 2023-09-13 → 2025-07-02; retorno 5.08%; trades 146
- validation: 2025-07-02 → 2026-02-06; retorno -2.80%; trades 49
- out_of_sample: 2026-02-06 → 2026-09-13; retorno 0.53%; trades 45

## Robustez de parâmetros (pesquisa, não escolha automática)

| EMA rápida | EMA lenta | Retorno | Trades |
|---:|---:|---:|---:|
| 18 | 45 | 3.46% | 172 |
| 19 | 48 | 4.13% | 154 |
| 20 | 50 | 5.08% | 146 |
| 21 | 52 | 5.48% | 138 |
| 22 | 55 | 4.87% | 132 |

## Walk-forward
- Folds calculados: 4
- Seleção feita somente na validação; OOS permanece intocado.

- Fold 1: EMA 18/45; OOS -2.53%; trades 22
- Fold 2: EMA 21/52; OOS -0.92%; trades 14
- Fold 3: EMA 21/52; OOS 0.20%; trades 15
- Fold 4: EMA 18/45; OOS 1.02%; trades 20

## Conclusão

Classificação: INCONCLUSIVA.

O baseline e o OOS devem ser avaliados com mais trades antes de qualquer decisão. Resultado positivo isolado não prova edge; amostras pequenas são apenas alerta de tamanho e não evidência de lucratividade.

Monte Carlo e regimes bull/bear/lateral ficam condicionados a uma amostra de trades maior que a atual.
