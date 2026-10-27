import numpy as np
import pandas as pd
import torch
from engine.multimodal_model import ForecastModel
from engine.technical_features import extract_technical_features
from engine.inference_service import get_forecast_for_symbol, simulate_forecast_whatif
from modules.modules import Chatterbot, FDCalculatorBot
from train_benchmark import partitions


def test_missing_news_gate_is_technical():
    torch.manual_seed(42)
    m = ForecastModel()
    m.eval()
    x = torch.randn(2, 20, 14)
    n = torch.randn(2, 7)
    n[:, 6] = 0
    with torch.no_grad():
        a = m(x, n)
        n[:, :6] = 100
        b = m(x, n)
    assert torch.equal(a, b)


def test_features_are_causal():
    rng = np.random.RandomState(1)
    c = 100 + np.cumsum(rng.randn(100))
    df = pd.DataFrame(
        dict(Close=c, Open=c, High=c + 1, Low=c - 1, Volume=np.ones(100) * 1000)
    )
    a = extract_technical_features(df.iloc[:80])
    b = extract_technical_features(df)
    np.testing.assert_allclose(a.values, b.iloc[:80].values)


def test_partition_purges_future_targets():
    d = list(pd.date_range("2025-01-01", periods=100))
    e = [x + pd.Timedelta(days=3) for x in d]
    tr, va, te = partitions(d, e)
    assert max(e[i] for i in tr) < min(d[i] for i in va)
    assert max(e[i] for i in va) < min(d[i] for i in te)


def test_emi_zero_and_reference():
    assert Chatterbot()._calculate_emi(12000, 0, 1) == (1000, 12000, 0)
    assert abs(Chatterbot()._calculate_emi(1000000, 8.5, 10)[0] - 12398.57) < 0.01


def test_fd_quarterly():
    assert FDCalculatorBot()._calculate_maturity(100000, 7, 365 * 5) == round(
        100000 * (1 + 0.07 / 4) ** 20, 2
    )


def test_unknown_and_invalid():
    assert get_forecast_for_symbol("INVALID")["status"] == "out_of_scope"
    assert simulate_forecast_whatif("TCS", float("nan"))["status"] == "invalid"


def test_supervised_training_updates_recurrent_weights():
    torch.manual_seed(42)
    model = ForecastModel(mode="technical")
    before = model.temporal.weight_ih_l0.detach().clone()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss = torch.nn.functional.cross_entropy(
        model(torch.randn(4, 20, 14), torch.zeros(4, 7)), torch.tensor([0, 1, 2, 0])
    )
    loss.backward()
    optimizer.step()
    assert not torch.equal(before, model.temporal.weight_ih_l0)


def test_recorded_results_match_prediction_files():
    import json
    from pathlib import Path
    from sklearn.metrics import confusion_matrix, f1_score

    files = list(Path("research/artifacts").glob("*_results.json"))
    assert len(files) >= 2
    for path in files:
        run = json.loads(path.read_text())
        predictions = pd.read_csv(
            str(path).replace("_results.json", "_predictions.csv")
        )
        for name, m in run["models"].items():
            rows = predictions[predictions.model == name]
            assert len(rows) == m["samples"]
            assert (
                confusion_matrix(rows.actual, rows.predicted, labels=[0, 1, 2]).tolist()
                == m["confusion_matrix"]
            )
            assert (
                abs(
                    f1_score(
                        rows.actual,
                        rows.predicted,
                        labels=[0, 1, 2],
                        average="macro",
                        zero_division=0,
                    )
                    - m["macro_f1"]
                )
                < 1e-12
            )
