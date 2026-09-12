# Risk controls

The central `RiskEngine` checks positive quantity/price, fresh market data,
concurrent positions, position exposure, total exposure, daily loss,
drawdown and available balance. Defaults are conservative technical gates for
testing, not a promise or recommendation of returns.

`SOFT STOP` blocks new positions. `HARD STOP` blocks new orders and is exposed
in the dashboard as `PARAR TODOS OS ROBÔS`; reactivation requires typing
`ENABLE`. LIVE remains locked independently of the UI.
