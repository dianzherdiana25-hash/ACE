"""D4 adversarial & edge-case tests for ACE research synthesis & verification modules.

Covers:
1. ace_egraph.equality_saturation
2. ace_smt.dpllt_solver
3. ace_conformal.conformal_risk
4. ace_pac_bayes.pac_bounds
5. ace_game_theory.minimax_synthesizer
6. ace_abstraction.wake_sleep
7. ace_automata.lstar

Genuine bugs discovered during edge-case testing are documented with
`@unittest.expectedFailure` without altering production module source files.
"""
from __future__ import annotations

import math
import unittest

from ace_abstraction.wake_sleep import DiscoveredPrimitive, WakeSleepAbstractionEngine
from ace_automata.lstar import DFA, LStarLearner
from ace_conformal.conformal_risk import (
    ConformalIntervalPredictor,
    ConformalRiskController,
    ConformalSetPredictor,
    compute_conformal_quantile,
    evaluate_coverage,
)
from ace_egraph.equality_saturation import (
    ASTDepthCost,
    ASTSizeCost,
    EClass,
    EGraph,
    ENode,
    EqualitySaturation,
    Extractor,
    Pattern,
    RewriteRule,
)
from ace_evolution.island_search import TypedASTNode
from ace_game_theory.minimax_synthesizer import (
    HedgePlayer,
    MinimaxCoEvolution,
    TwoPlayerGameMatrix,
)
from ace_pac_bayes.pac_bounds import (
    PACBayesCertifier,
    ProgramEnsembleDistribution,
    binary_kl,
    catoni_bound,
    invert_binary_kl,
    mcallester_bound,
    seeger_maurer_bound,
)
from ace_smt.dpllt_solver import (
    Assign,
    Const,
    DPLLTSolver,
    Eq,
    Ge,
    Gt,
    LinearConstraint,
    Literal,
    Lt,
    Mul,
    Ne,
    Sub,
    TheorySolver,
    Var,
    verify_program_satisfies_spec,
)


class TestEGraphEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_egraph.equality_saturation."""

    def test_01_pattern_parse_empty_sexpr_and_negative_constants(self):
        with self.assertRaises(ValueError):
            Pattern.parse("()")
        with self.assertRaises(ValueError):
            Pattern.parse("(   )")

        neg_pat = Pattern.parse("-5")
        self.assertEqual(neg_pat.op, "int_const")
        self.assertEqual(neg_pat.val, -5)

        ast = TypedASTNode(
            "add",
            "INT",
            children=[
                TypedASTNode("int_const", "INT", val=-5),
                TypedASTNode("int_const", "INT", val=5),
            ],
        )
        opt, _ = EqualitySaturation().rewrite(ast)
        self.assertEqual(opt.op, "int_const")
        self.assertEqual(opt.val, 0)

    def test_02_rewrite_rule_unbound_var_and_false_condition(self):
        egraph = EGraph()
        x_cls = egraph.add_ast(TypedASTNode("count_a", "INT"))
        unbound_rule = RewriteRule(
            name="unbound",
            lhs=Pattern.parse("?x"),
            rhs=Pattern.parse("(add ?x ?missing)"),
        )
        with self.assertRaises(ValueError):
            unbound_rule.apply(egraph, x_cls, {"x": x_cls})

        blocked_rule = RewriteRule(
            name="never-fires",
            lhs=Pattern.parse("?x"),
            rhs=Pattern.parse("0"),
            condition=lambda s, g: False,
        )
        self.assertIsNone(blocked_rule.apply(egraph, x_cls, {"x": x_cls}))

    def test_03_shared_var_matching_and_transitive_congruence_closure(self):
        egraph = EGraph()
        a = egraph.add_ast(TypedASTNode("count_a", "INT"))
        b = egraph.add_ast(TypedASTNode("count_b", "INT"))
        c = egraph.add_ast(TypedASTNode("len", "INT"))

        eq_ab = egraph.add_node(ENode("eq", children=(a, b), return_type="BOOL"))
        same_pat = Pattern.parse("(eq ?x ?x)")
        self.assertEqual(list(same_pat.match_class(egraph, eq_ab, {})), [])

        fa = egraph.add_node(ENode("not", children=(a,), return_type="INT"))
        fc = egraph.add_node(ENode("not", children=(c,), return_type="INT"))
        ffa = egraph.add_node(ENode("not", children=(fa,), return_type="INT"))
        ffc = egraph.add_node(ENode("not", children=(fc,), return_type="INT"))

        egraph.union(a, b)
        egraph.union(b, c)
        repairs = egraph.rebuild()
        self.assertGreaterEqual(repairs, 1)
        self.assertEqual(egraph.find(ffa), egraph.find(ffc))
        self.assertEqual(len(list(same_pat.match_class(egraph, eq_ab, {}))), 1)

    def test_04_ungrounded_cycle_extract_raises_and_cost_functions(self):
        egraph_cyc = EGraph()
        x = egraph_cyc.union_find.make_set()
        enode = ENode("not", children=(x,), return_type="INT")
        egraph_cyc.classes[x] = EClass(x)
        egraph_cyc.classes[x].nodes.add(enode)
        extractor = Extractor(egraph_cyc, ASTDepthCost())
        with self.assertRaises(ValueError):
            extractor.extract(x)

        c_ast = TypedASTNode("int_const", "INT", val=0)
        v_ast = TypedASTNode("count_a", "INT")
        cost_fn = ASTSizeCost(constant_discount=0.25)
        self.assertLess(cost_fn.compute_ast_cost(c_ast), cost_fn.compute_ast_cost(v_ast))

    def test_05_bool_const_not_int_folded_and_node_limit_respect(self):
        ast = TypedASTNode(
            "add",
            "INT",
            children=[
                TypedASTNode("bool_const", "BOOL", val=True),
                TypedASTNode("int_const", "INT", val=1),
            ],
        )
        egraph = EGraph()
        root_id = egraph.add_ast(ast)
        report = EqualitySaturation().run(egraph, root_id, node_limit=1)
        self.assertFalse(report.saturated)
        opt = Extractor(egraph).extract(root_id)
        self.assertEqual(opt.op, "add")


class TestDPLLTSolverEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_smt.dpllt_solver."""

    def setUp(self):
        self.solver = DPLLTSolver()
        self.theory = TheorySolver()

    def test_06_chvatal_gomory_negative_floor_and_empty_coeffs(self):
        # 2x <= -3 in integers implies x <= -2 (floor(-1.5) == -2)
        c1 = LinearConstraint.from_le({"x": 2}, -3, "c1")
        self.assertEqual(c1.coeffs, {"x": 1})
        self.assertEqual(c1.const, -2)

        c2 = LinearConstraint.from_ge({"x": 1}, -1, "c2")
        consistent, core, _ = self.theory.check_consistency([(c1, True, "c1"), (c2, True, "c2")])
        self.assertFalse(consistent)
        self.assertEqual(core, {"c1", "c2"})

        false_c = LinearConstraint.from_le({}, -1, "false_c")
        consistent2, core2, _ = self.theory.check_consistency([(false_c, True, "false_c")])
        self.assertFalse(consistent2)
        self.assertEqual(core2, {"false_c"})

        true_c = LinearConstraint.from_le({}, 0, "true_c")
        consistent3, _, model3 = self.theory.check_consistency([(true_c, True, "true_c")])
        self.assertTrue(consistent3)
        self.assertEqual(model3, {})

    def test_07_empty_cnf_empty_clause_and_tautology(self):
        res_empty_clause = self.solver.solve([[]], {})
        self.assertFalse(res_empty_clause.is_sat)
        self.assertEqual(res_empty_clause.decisions, 0)

        res_empty_cnf = self.solver.solve([], {})
        self.assertTrue(res_empty_cnf.is_sat)
        self.assertEqual(res_empty_cnf.integer_model, {})

        res_taut = self.solver.solve([[Literal("a", True), Literal("a", False)]], {})
        self.assertTrue(res_taut.is_sat)

    def test_08_t_propagation_deduces_negated_literal_and_irrelevant_isolation(self):
        t1 = LinearConstraint.from_le({"x": 1}, 2, "t1")
        t2 = LinearConstraint.from_ge({"x": 1}, 5, "t2")
        t_irrel = LinearConstraint.from_ge({"z": 1}, 10, "t_irrel")

        res = self.solver.solve(
            [[Literal("t1", True)], [Literal("t_irrel", True)]],
            {"t1": t1, "t2": t2, "t_irrel": t_irrel},
            enable_t_propagation=True,
        )
        self.assertTrue(res.is_sat)
        self.assertFalse(res.boolean_assignment["t2"])
        self.assertGreater(res.theory_propagations, 0)
        self.assertLessEqual(res.integer_model["x"], 2)
        self.assertGreaterEqual(res.integer_model["z"], 10)

        cons, core, _ = self.theory.check_consistency(
            [(t1, True, "t1"), (t2, True, "t2"), (t_irrel, True, "t_irrel")]
        )
        self.assertFalse(cons)
        self.assertEqual(core, {"t1", "t2"})

    def test_09_ssa_phi_else_none_dict_statements_and_nonlinear_rejection(self):
        prog = {
            "if": Lt(Var("x"), Const(0)),
            "then": {"assign": "x", "expr": Sub(Const(0), Var("x"))},
        }
        v_valid = verify_program_satisfies_spec(prog, pre_cond=None, post_cond=Ge(Var("x"), Const(0)))
        self.assertTrue(v_valid.is_valid)

        prog_scale = Assign("y", Mul(Const(2), Var("x")))
        v_scale = verify_program_satisfies_spec(prog_scale, pre_cond=Ge(Var("x"), Const(3)), post_cond=Ge(Var("y"), Const(6)))
        self.assertTrue(v_scale.is_valid)

        prog_nonlin = Assign("y", Mul(Var("x"), Var("x")))
        with self.assertRaises(ValueError):
            verify_program_satisfies_spec(prog_nonlin, pre_cond=None, post_cond=Ge(Var("y"), Const(0)))

    def test_10_bug_verifier_eq_missing_lower_bound(self):
        # BUG (dpllt_solver.py:758-762): Eq encodes ONLY left <= right, omitting left >= right.
        # x == 5 => y == x => y >= 5 is valid, yet solver finds counterexample x = 0.
        # DIPERBAIKI (gelombang robustness 2026-11-20): Eq/Ne dienkode Tseitin (b <=> le /\ ge).
        prog = Assign("y", Var("x"))
        res = verify_program_satisfies_spec(
            prog,
            pre_cond=Eq(Var("x"), Const(5)),
            post_cond=Ge(Var("y"), Const(5)),
        )
        self.assertTrue(res.is_valid)

    def test_11_bug_verifier_ne_condition_crashes_unsupported(self):
        # BUG (dpllt_solver.py:735-768): Ne is listed in tuple check at L735 but unhandled,
        # raising ValueError instead of encoding x != 0.
        # DIPERBAIKI (gelombang robustness 2026-11-20): Ne = negasi literal Tseitin Eq.
        prog = Assign("y", Var("x"))
        res = verify_program_satisfies_spec(
            prog,
            pre_cond=Gt(Var("x"), Const(0)),
            post_cond=Ne(Var("y"), Const(0)),
        )
        self.assertTrue(res.is_valid)


class TestConformalRiskEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_conformal.conformal_risk."""

    def test_12_conformal_quantile_empty_small_n_and_alpha_clamping(self):
        with self.assertRaises(ValueError):
            compute_conformal_quantile([], alpha=0.10)

        self.assertEqual(compute_conformal_quantile([3.5], alpha=0.10), float("inf"))
        self.assertEqual(compute_conformal_quantile([3.5], alpha=0.50), 3.5)

        scores = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(compute_conformal_quantile(scores, alpha=-0.5), float("inf"))
        self.assertEqual(compute_conformal_quantile(scores, alpha=1.5), 1.0)

    def test_13_uncalibrated_predictors_raise_runtime_error(self):
        interval_p = ConformalIntervalPredictor(point_predictor=lambda x: float(x))
        set_p = ConformalSetPredictor(score_model=lambda x: {"A": 0.9})
        ctrl = ConformalRiskController(set_generator=lambda x, l: {x}, loss_fn=lambda c, y: 0.0)

        with self.assertRaises(RuntimeError):
            interval_p.predict_interval(1.0)
        with self.assertRaises(RuntimeError):
            set_p.predict_set(1)
        with self.assertRaises(RuntimeError):
            ctrl.predict(1)

    def test_14_controller_empty_calibration_and_conservative_fallback(self):
        ctrl = ConformalRiskController(
            set_generator=lambda x, l: (x - l, x + l),
            loss_fn=lambda interval, y: 0.0 if interval[0] <= y <= interval[1] else 1.0,
            loss_bound_B=1.0,
            target_risk_alpha=0.0,
        )
        with self.assertRaises(ValueError):
            ctrl.calibrate([], [0.5, 1.0])

        lam = ctrl.calibrate([(0.0, 0.0), (1.0, 1.0)], [2.0, 0.5, 1.0])
        self.assertEqual(lam, 2.0)

    def test_15_bug_controller_empty_lambda_candidates_index_error(self):
        # BUG (conformal_risk.py:131): empty lambda_candidates triggers raw IndexError
        # instead of ValueError validation.
        # DIPERBAIKI (gelombang robustness 2026-11-20): calibrate menolak lambda_candidates kosong dengan ValueError.
        ctrl = ConformalRiskController(
            set_generator=lambda x, l: {x},
            loss_fn=lambda c, y: 0.0,
        )
        with self.assertRaises(ValueError):
            ctrl.calibrate([(1, 1)], lambda_candidates=[])

    def test_16_evaluate_coverage_empty_and_zero_width_intervals(self):
        res_empty = evaluate_coverage(lambda x: {x}, [])
        self.assertEqual(res_empty["coverage"], 1.0)
        self.assertEqual(res_empty["average_size"], 0.0)

        res_inv = evaluate_coverage(lambda x: (5.0, 3.0), [(1, 4.0), (2, 5.0)], is_interval=True)
        self.assertEqual(res_inv["coverage"], 0.0)
        self.assertEqual(res_inv["average_size"], 0.0)


class TestPACBayesEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_pac_bayes.pac_bounds."""

    def test_17_invalid_m_and_catoni_c_raise_value_error(self):
        for m_bad in (0, -5):
            with self.assertRaises(ValueError):
                mcallester_bound(0.1, 0.5, m_bad)
            with self.assertRaises(ValueError):
                seeger_maurer_bound(0.1, 0.5, m_bad)
            with self.assertRaises(ValueError):
                catoni_bound(0.1, 0.5, m_bad)

        with self.assertRaises(ValueError):
            catoni_bound(0.1, 0.5, 100, c=0.0)
        with self.assertRaises(ValueError):
            catoni_bound(0.1, 0.5, 100, c=2.0)

        ens = ProgramEnsembleDistribution(["p"], [lambda x: x], [1.0])
        with self.assertRaises(ValueError):
            PACBayesCertifier().certify(ens, dataset=[])

    def test_18_binary_kl_and_invert_boundaries(self):
        self.assertEqual(binary_kl(-0.5, 0.5), binary_kl(0.0, 0.5))
        self.assertAlmostEqual(binary_kl(1.0, 1.0), 0.0, places=5)
        self.assertGreater(binary_kl(1.0, 0.5), 0.0)
        self.assertEqual(invert_binary_kl(1.0, 0.5), 1.0)
        self.assertEqual(invert_binary_kl(0.1, 100.0), 1.0)
        self.assertFalse(math.isnan(invert_binary_kl(0.5, -1.0)))

    def test_19_gibbs_posterior_zero_and_extreme_temperature_stability(self):
        ens = ProgramEnsembleDistribution(
            program_ids=["good", "bad"],
            programs=[lambda x: x, lambda x: -x],
            prior_weights=[0.3, 0.7],
        )
        ens.update_to_gibbs_posterior([0.0, 1.0], m=100, temperature=0.0)
        self.assertAlmostEqual(ens.compute_kl_divergence(), 0.0, places=9)
        self.assertAlmostEqual(ens.posterior_weights[0], 0.3, places=9)

        ens.update_to_gibbs_posterior([0.0, 1.0], m=10000, temperature=1e4)
        self.assertTrue(all(math.isfinite(w) for w in ens.posterior_weights))
        self.assertAlmostEqual(sum(ens.posterior_weights), 1.0, places=9)
        self.assertGreater(ens.posterior_weights[0], 0.99)

    def test_20_zero_prior_and_nonpositive_posterior_fallbacks(self):
        ens = ProgramEnsembleDistribution(
            program_ids=["p1", "p2"],
            programs=[lambda x: 0, lambda x: 1],
            prior_weights=[0.0, 0.0],
            posterior_weights=[-1.0, -2.0],
        )
        self.assertAlmostEqual(ens.prior_weights[0], 0.5)
        self.assertAlmostEqual(ens.posterior_weights[0], 0.5)
        self.assertEqual(ens.evaluate_empirical_risks([]), [0.0, 0.0])

    def test_21_bug_empty_ensemble_zero_division(self):
        # BUG (pac_bounds.py:162): empty program_ids raises raw ZeroDivisionError instead of ValueError.
        # DIPERBAIKI (gelombang robustness 2026-11-20): __post_init__ menolak program_ids kosong dengan ValueError.
        with self.assertRaises(ValueError):
            ProgramEnsembleDistribution(program_ids=[], programs=[], prior_weights=[])


class TestMinimaxSynthesizerEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_game_theory.minimax_synthesizer."""

    def test_22_game_matrix_validation_and_asymmetric_dimensions(self):
        with self.assertRaises(ValueError):
            TwoPlayerGameMatrix([])
        with self.assertRaises(ValueError):
            TwoPlayerGameMatrix([[0.1, 0.2], [0.3]])

        game = TwoPlayerGameMatrix([[0.2, 0.8, 0.4], [0.6, 0.1, 0.9]])
        p = [0.5, 0.5]
        q = [0.2, 0.3, 0.5]
        s_vec = game.synthesizer_payoff_vector(q)
        a_vec = game.adversary_payoff_vector(p)
        self.assertEqual(len(s_vec), 2)
        self.assertEqual(len(a_vec), 3)
        expected = sum(p[i] * s_vec[i] for i in range(2))
        self.assertAlmostEqual(game.expected_payoff(p, q), expected, places=9)

    def test_23_from_programs_loss_clipping_and_1x1_game(self):
        engine = MinimaxCoEvolution.from_programs_and_inputs(
            programs=[lambda x: x],
            adversarial_inputs=[1],
            oracle_evaluator=lambda p, x: 42.0 if p(x) == 1 else -3.0,
        )
        self.assertEqual(engine.game.matrix, [[1.0]])
        res = engine.solve(rounds=5)
        self.assertAlmostEqual(res["duality_gap"], 0.0, places=9)
        self.assertEqual(res["game_value_V"], 1.0)

    def test_24_hedge_extreme_eta_numerical_stability(self):
        player = HedgePlayer(num_actions=3, is_minimizer=True, eta=1e4)
        for _ in range(10):
            player.update([100.0, 0.0, 50.0])
        strat = player.current_strategy
        self.assertTrue(all(math.isfinite(s) for s in strat))
        self.assertAlmostEqual(sum(strat), 1.0, places=9)
        self.assertGreater(strat[1], 0.99)

    def test_25_bug_hedge_compute_regret_uses_final_strategy_not_realized_loss(self):
        # BUG (minimax_synthesizer.py:124-141): strategy_history loop is a `pass` stub,
        # evaluating final current_strategy instead of realized sum_t <p_t, loss_t>.
        # Realized loss = 0.5*1 + (e/(1+e))*1 ~= 1.23106 vs best fixed = 1.0 (regret > 0.2).
        # DIPERBAIKI (gelombang robustness 2026-11-20): update() mengakumulasi realized_loss <p_t, cost_t>.
        player = HedgePlayer(num_actions=2, is_minimizer=True, eta=1.0)
        player.update([1.0, 0.0])
        player.update([0.0, 1.0])
        self.assertGreater(player.compute_regret(), 0.2)

    def test_26_bug_minimax_solve_zero_rounds_raises_value_error(self):
        # BUG (minimax_synthesizer.py:161): rounds=0 fails with ZeroDivisionError instead of ValueError.
        # DIPERBAIKI (gelombang robustness 2026-11-20): solve menolak rounds <= 0 dengan ValueError.
        engine = MinimaxCoEvolution(TwoPlayerGameMatrix([[0.5]]))
        with self.assertRaises(ValueError):
            engine.solve(rounds=0)


class TestWakeSleepEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_abstraction.wake_sleep."""

    def test_27_empty_solutions_and_high_min_support(self):
        engine = WakeSleepAbstractionEngine()
        res_empty = engine.sleep_abstract_library(min_support=2)
        self.assertEqual(res_empty["solutions_processed"], 0)
        self.assertFalse(res_empty["transfer_ready"])
        self.assertEqual(res_empty["compression_ratio"], 1.0)

        node = TypedASTNode(
            "add",
            "INT",
            children=[TypedASTNode("count_a", "INT"), TypedASTNode("int_const", "INT", val=1)],
        )
        engine.record_solution("t1", node)
        res_high = engine.sleep_abstract_library(min_support=3)
        self.assertEqual(res_high["new_primitives_promoted"], [])
        self.assertFalse(res_high["transfer_ready"])

    def test_28_sandbox_blocks_builtins_and_bool_unary_anti_unification(self):
        bad_prim = DiscoveredPrimitive(
            name="evil",
            parameter_names=[],
            template_expr="__import__('os').getcwd()",
        )
        with self.assertRaises(Exception):
            bad_prim.evaluate("abc")

        engine = WakeSleepAbstractionEngine()
        for val in (True, False):
            ast = TypedASTNode(
                "not",
                "BOOL",
                children=[
                    TypedASTNode(
                        "and",
                        "BOOL",
                        children=[
                            TypedASTNode(
                                "eq",
                                "BOOL",
                                children=[TypedASTNode("count_a", "INT"), TypedASTNode("int_const", "INT", val=2)],
                            ),
                            TypedASTNode("bool_const", "BOOL", val=val),
                        ],
                    )
                ],
            )
            engine.record_solution(f"b_{val}", ast)

        res = engine.sleep_abstract_library(min_support=2)
        self.assertTrue(res["transfer_ready"])
        prim = engine.discovered_primitives[res["new_primitives_promoted"][0]]
        if len(prim.parameter_names) == 2:
            self.assertFalse(prim.evaluate("aa", 2, True))
            self.assertTrue(prim.evaluate("aa", 2, False))
        else:
            self.assertTrue(prim.evaluate("aa", 2))

    def test_29_repeated_sleep_idempotent_library_promotion(self):
        engine = WakeSleepAbstractionEngine()
        for idx, k in enumerate((2, 3)):
            engine.record_solution(
                f"s{idx}",
                TypedASTNode("add", "INT", children=[TypedASTNode("count_b", "INT"), TypedASTNode("int_const", "INT", val=k)]),
            )
        first = engine.sleep_abstract_library(min_support=2)
        second = engine.sleep_abstract_library(min_support=2)
        self.assertEqual(len(first["new_primitives_promoted"]), 1)
        self.assertEqual(second["new_primitives_promoted"], [])
        self.assertEqual(second["total_library_size"], 1)

    def test_30_bug_len_primitive_template_fails_sandbox_eval(self):
        # BUG (wake_sleep.py:29): TypedASTNode('len', 'INT').to_code() compiles to 'len(word)',
        # yet DiscoveredPrimitive.evaluate uses {'__builtins__': None} without supplying len in scope.
        # DIPERBAIKI (gelombang robustness 2026-11-20): evaluate memasok len/max — seluruh kosakata callable to_code.
        engine = WakeSleepAbstractionEngine()
        for idx, k in enumerate((1, 5)):
            engine.record_solution(
                f"len_task_{idx}",
                TypedASTNode("add", "INT", children=[TypedASTNode("len", "INT"), TypedASTNode("int_const", "INT", val=k)]),
            )
        res = engine.sleep_abstract_library(min_support=2)
        prim = engine.discovered_primitives[res["new_primitives_promoted"][0]]
        self.assertEqual(prim.evaluate("abc", 4), 7)


class TestLStarAutomataEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_automata.lstar."""

    def test_31_empty_alphabet_learns_single_state_dfa(self):
        learner = LStarLearner(alphabet=())
        dfa = learner.learn(lambda s: s == "")
        self.assertEqual(len(dfa.states), 1)
        self.assertTrue(dfa.run(""))
        self.assertFalse(dfa.run("a"))
        self.assertEqual(dfa.to_r1_signature(), [[True, []]])
        scope = {}
        exec(dfa.to_python_code("only_empty"), scope)
        self.assertTrue(scope["only_empty"](""))
        self.assertFalse(scope["only_empty"]("a"))

    def test_32_out_of_alphabet_and_partial_transition_dfa(self):
        dfa = LStarLearner(alphabet=("a", "b")).learn(lambda s: s.count("a") % 2 == 0)
        self.assertFalse(dfa.run("az"))

        partial = DFA(
            states=[0, 1],
            alphabet=("a", "b"),
            transitions={(0, "a"): 1},
            initial_state=0,
            accepting_states={1},
        )
        self.assertTrue(partial.run("a"))
        self.assertFalse(partial.run("b"))
        self.assertFalse(partial.run("ab"))

    def test_33_max_states_bounds_non_regular_language(self):
        teacher = lambda s: s.count("a") == s.count("b")
        samples = [("", True), ("ab", True), ("aabb", True), ("aaabbb", True), ("aab", False)]
        dfa = LStarLearner(alphabet=("a", "b")).learn(
            teacher,
            training_samples=samples,
            max_states=4,
            max_iterations=10,
        )
        self.assertGreaterEqual(len(dfa.states), 1)
        self.assertLessEqual(len(dfa.states), 8)

    def test_34_bug_to_python_code_ignores_nonzero_initial_state(self):
        # BUG (lstar.py:54): to_python_code hardcodes `state = 0` instead of `self.initial_state`.
        # DIPERBAIKI (gelombang robustness 2026-11-20): kode yang dibangkitkan memakai self.initial_state.
        dfa = DFA(
            states=[0, 1, 2],
            alphabet=("a",),
            transitions={(1, "a"): 2},
            initial_state=1,
            accepting_states={2},
        )
        self.assertTrue(dfa.run("a"))
        scope = {}
        exec(dfa.to_python_code("start_at_one"), scope)
        self.assertEqual(scope["start_at_one"]("a"), dfa.run("a"))


if __name__ == "__main__":
    unittest.main()
