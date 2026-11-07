# ACE F11 Active Epistemic Querying: Critical Re-Audit & Leakage Analysis

**Status:** AUDIT COMPLETE & FINDINGS REGISTERED  
**Target:** F11 Active Epistemic Querying Pilot (`code/ace_research_active/`)  
**Auditor:** Lead Research Engineer & Autonomous Development Coordinator (Gemini Argon)  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Date:** 2026-11-07  

---

## 1. Executive Summary & Audit Scope

Following the successful execution of the F11 Active Epistemic Querying (AEQ) pilot in Draft PR #78, an adversarial review was conducted to evaluate the scientific validity of the experimental design. Specifically, three critical questions were investigated:
1. **Was there oracle leakage into the probe synthesis mechanism?**
2. **Was external environment/oracle query access strictly metered?**
3. **Were semantic drift triggers non-trivial and structurally representative of real capability shifts?**

---

## 2. Finding 1: Unmetered Oracle Leakage in Reference Function

### 2.1 Code Vulnerability Analysis
In `code/ace_research_active/harness.py` lines 122–123:
```python
candidate = make_drift_candidate()
# Reference specification: simple baseline model
reference = true_pred
```
Here, `reference` was initialized directly as `true_pred` (the ground-truth oracle).

Subsequently, in `code/ace_research_active/prober.py` lines 56–85, `synthesize_discriminating_probes` evaluated candidate divergence:
```python
if bool(candidate_fn(q)) != bool(reference_fn(q)):
    differentiating.append(q)
```

### 2.2 Epistemic Consequence
Because `reference_fn` was pointing to the ground truth oracle `true_pred`, the prober was evaluating the true oracle offline over hundreds of neighborhood mutations and combinatorial short strings ($q \in \Sigma^{\le 6}$) **without consuming the query budget**. Only after the discriminating inputs were identified was the oracle invoked in the benchmark loop.

In a realistic open-ended research setting:
- An autonomous agent exploring an unknown domain **does not have access to the true oracle** during candidate hypothesis generation or offline probe selection.
- The reference model $M_{\text{ref}}$ can only be the agent's prior hypothesis $M_{\text{base}}$ ($G_0$), an ensemble of diverse prior hypotheses, or an explicit specification contract.
- Any observation of the true environment state $O(q)$ must be an **external epistemic query** strictly metered against an operational compute/query budget.

---

## 3. Finding 2: Unmetered Query Consumption

In the F11 pilot, the query budget parameter ($K \in \{0, 4, 8, 16\}$) metered only the final test evaluations on `differentiating` inputs. The unmetered offline evaluations of `reference_fn` inside `synthesize_discriminating_probes` allowed the synthesizer to execute up to $2^6 = 64$ offline oracle checks for free.

In F12, query accounting is governed strictly by the **Independent Host Controller** (`code/ace_host_controller/budget_permits.py`). Every query to the environment oracle $O(q)$ increments `ExecutionBudget.used_queries` by 1. If `used_queries > max_queries`, execution fails closed with `BudgetExceededError`.

---

## 4. Finding 3: Trivial String Keywords vs Structural Triggers

The 10 adversarial semantic drift triggers in F11 relied predominantly on simple string substrings (e.g. `w.startswith("bbb")`, `"babb" in w`, `w.endswith("aaa")`). While sufficient for demonstrating length-gated drift, these triggers are easily exposed by 1-edit neighborhood mutations.

Real-world capability shifts and inductive biases exhibit deeper structural properties:
1. **Modular Parity & Stride Invariants:**
   $$w[0::2].\text{count}('a') \pmod 3 == 0$$
   Requires tracking state over alternating positions.
2. **Context-Free / Hierarchical Balance (Dyck Languages):**
   Equal count and non-negative prefix balance ($\text{depth}(w) \ge 0 \land \text{depth}(w) == 0$).
3. **Relational Constraints:**
   Prefix-suffix symmetry or length-modulo divisibility.

---

## 5. Architectural Mandate for F12 Causal Autonomous Research

To achieve true scientific validity without leakage or overclaiming, **F12 Causal Autonomous Research** (`code/ace_research_f12/`) enforces:

1. **Zero Oracle Leakage:**
   - Candidate generator only possesses its prior hypothesis $M_{\text{base}}$ ($G_0$) and past evidence.
   - Oracle $O$ is external, sealed inside the Host Controller.
2. **Metered Host Controller Governance:**
   - All environment inquiries pass through `HostController.budget.consume_queries(1)`.
   - All candidates are registered in `LineageGraph` with source SHA and generation depth.
   - Non-contamination is verified by `ExposureLedger`.
3. **Structural Non-Trivial Task Families:**
   - Evaluated across diverse algorithmic families (modular parity, strided counting, Dyck bracket balance, prefix/suffix relations).
4. **Matched Controls:**
   - Fixed research templates
   - Random hypothesis/experiment policy
   - Passive evaluation (no queries)
   - Active information-gain F12
   - Extra-compute control
   - No-memory and shuffled-memory ablations
