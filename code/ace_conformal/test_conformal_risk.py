"""Unit tests for Conformal Risk Control & Distribution-Free Prediction Sets."""
from __future__ import annotations

import random
import unittest
from ace_conformal.conformal_risk import (
    ConformalIntervalPredictor,
    ConformalRiskController,
    ConformalSetPredictor,
    compute_conformal_quantile,
    evaluate_coverage,
)


class TestConformalRisk(unittest.TestCase):
    def test_conformal_quantile_finite_sample_correction(self):
        # n = 99, alpha = 0.10 -> (99 + 1) * 0.90 = 90-th order statistic
        scores = list(range(1, 100))  # 1 to 99
        q = compute_conformal_quantile(scores, alpha=0.10)
        self.assertEqual(q, 90)

        # n = 9, alpha = 0.10 -> (9 + 1) * 0.90 = 9-th order statistic
        scores_small = list(range(1, 10))  # 1 to 9
        q_small = compute_conformal_quantile(scores_small, alpha=0.10)
        self.assertEqual(q_small, 9)

        # If alpha is extremely small and requires more samples than n
        q_inf = compute_conformal_quantile([1.0, 2.0], alpha=0.01)
        self.assertEqual(q_inf, float("inf"))

    def test_conformal_interval_predictor_coverage(self):
        # Synthetic noisy program execution time: y = 2.5 * x + noise
        rng = random.Random(42)

        def generate_data(n: int):
            data = []
            for _ in range(n):
                x = rng.uniform(1.0, 10.0)
                # Non-Gaussian, asymmetric log-normal noise
                noise = rng.lognormvariate(0.0, 0.5)
                y = 2.5 * x + noise
                data.append((x, y))
            return data

        cal_data = generate_data(200)
        test_data = generate_data(800)

        # Point predictor (slightly imperfect)
        model = lambda x: 2.5 * x + 1.0

        predictor = ConformalIntervalPredictor(point_predictor=model, alpha=0.10)
        q_hat = predictor.calibrate(cal_data)
        self.assertGreater(q_hat, 0.0)

        eval_res = evaluate_coverage(predictor.predict_interval, test_data, is_interval=True)
        # Target coverage >= 1 - alpha = 0.90 (allow small Monte Carlo slack >= 0.88)
        self.assertGreaterEqual(eval_res["coverage"], 0.88)
        self.assertLessEqual(eval_res["coverage"], 0.95)
        # Average interval size should be non-vacuous (< 6.0)
        self.assertLess(eval_res["average_size"], 6.0)

    def test_conformal_set_predictor_discrete_coverage(self):
        # 5-class discrete categorization problem
        classes = ["INT", "BOOL", "STRING", "LIST", "DICT"]
        rng = random.Random(123)

        def mock_classifier(x: int) -> dict:
            # Model outputs probability distribution
            true_idx = x % 5
            dist = {c: 0.05 for c in classes}
            dist[classes[true_idx]] = 0.80
            return dist

        def generate_class_data(n: int):
            data = []
            for _ in range(n):
                x = rng.randint(1, 1000)
                true_label = classes[x % 5]
                data.append((x, true_label))
            return data

        cal_data = generate_class_data(250)
        test_data = generate_class_data(1000)

        predictor = ConformalSetPredictor(score_model=mock_classifier, alpha=0.05)
        q_hat = predictor.calibrate(cal_data)

        eval_res = evaluate_coverage(predictor.predict_set, test_data, is_interval=False)
        # Target coverage >= 1 - alpha = 0.95
        self.assertGreaterEqual(eval_res["coverage"], 0.94)
        # Average set size must be non-vacuous (strictly less than full set of 5 classes)
        self.assertLess(eval_res["average_size"], 2.0)
        self.assertGreaterEqual(eval_res["average_size"], 1.0)

    def test_conformal_risk_controller_learn_then_test(self):
        # Monotonic risk control: thresholding confidence parameter lambda
        rng = random.Random(999)

        # Set generator: expands prediction window as lambda grows
        def set_gen(x: float, lam: float):
            return (x - lam, x + lam)

        # Loss function: 0 if y in interval, else 1.0
        def loss(interval, y):
            low, high = interval
            return 0.0 if low <= y <= high else 1.0

        def gen_samples(n: int):
            return [(x, x + rng.gauss(0.0, 1.5)) for x in [rng.uniform(0, 50) for _ in range(n)]]

        cal_set = gen_samples(300)
        test_set = gen_samples(1000)

        # Target risk <= 0.10
        controller = ConformalRiskController(
            set_generator=set_gen,
            loss_fn=loss,
            loss_bound_B=1.0,
            target_risk_alpha=0.10,
        )

        candidate_lambdas = [i * 0.1 for i in range(1, 50)]
        cal_lam = controller.calibrate(cal_set, candidate_lambdas)
        self.assertGreater(cal_lam, 0.0)

        # Test on independent test set
        test_losses = [loss(controller.predict(x), y) for x, y in test_set]
        empirical_test_risk = sum(test_losses) / len(test_losses)

        # Guaranteed risk control: test risk <= alpha = 0.10
        self.assertLessEqual(empirical_test_risk, 0.11)


if __name__ == "__main__":
    unittest.main()
