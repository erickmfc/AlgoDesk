import pytest
from src.config_loader import paper_engine_config_from_yaml, risk_config_from_yaml


def test_versioned_yaml_controls_load_into_runtime_configs(tmp_path):
    risk_path = tmp_path / "risk.yaml"
    risk_path.write_text("risk:\n  max_position_percent: 7.5\n", encoding="utf-8")
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(
        "strategy:\n"
        "  id: test-ema\n"
        "  symbol: ETHUSDT\n"
        "  interval: 15m\n"
        "  fast_ema: 8\n"
        "  slow_ema: 21\n"
        "  atr_period: 10\n"
        "  stop_loss_atr: 1.5\n"
        "  take_profit_atr: 2.5\n",
        encoding="utf-8",
    )

    risk = risk_config_from_yaml(str(risk_path))
    strategy = paper_engine_config_from_yaml(str(strategy_path))

    assert risk.max_position_percent == 7.5
    assert strategy.strategy_id == "test-ema"
    assert strategy.symbol == "ETHUSDT"
    assert strategy.interval == "15m"
    assert (strategy.fast_period, strategy.slow_period) == (8, 21)
    assert strategy.atr_period == 10
    assert (strategy.stop_loss_atr, strategy.take_profit_atr) == (1.5, 2.5)


def test_unknown_risk_configuration_fails_closed(tmp_path):
    path = tmp_path / "risk.yaml"
    path.write_text("risk:\n  unsupported_switch: true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported risk configuration"):
        risk_config_from_yaml(str(path))


def test_unknown_strategy_configuration_fails_closed(tmp_path):
    path = tmp_path / "strategy.yaml"
    path.write_text("strategy:\n  unsupported_switch: true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported strategy configuration"):
        paper_engine_config_from_yaml(str(path))
