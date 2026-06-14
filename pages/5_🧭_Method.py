"""Exam Method page — how to plan and write answers that score.

A fast in-exam reference: the universal answer-planning method, the time
budget, command-word decoding, and the per-topic answer skeletons / mnemonics
that examiners reward (condensed from the Trainer's Playbook).
"""
import streamlit as st
from cs1 import auth

st.set_page_config(page_title="Method - CS1", page_icon="🧭", layout="wide")
auth.require_login()
auth.logout_button()

st.title("🧭 Exam Method & Answer Planning")
st.caption("Most lost marks are method, not knowledge: not answering the question asked, "
           "not interpreting in context, half-remembered R. This page is the fix — skim it "
           "before a practice paper and keep the skeletons automatic.")

# ---------------------------------------------------------------- the universal method
st.subheader("The 5-step method for any question")
st.markdown("""
1. **Read the command word.** *Calculate / derive / show* = produce maths.
   *State / write down* = no working needed. *Comment / interpret / explain* = a
   sentence applying the result **in context** — this is where applied marks live.
2. **Name the method before you compute.** Identify the topic and the technique
   (which test? which distribution? which estimator?). Choosing the right method
   is half the marks.
3. **State assumptions / set-up.** Hypotheses, distributional assumptions, the
   formula you're about to use.
4. **Execute cleanly.** Show the substitution, not just the final number — method
   marks survive an arithmetic slip.
5. **Interpret in context + check the marks.** End with a plain-English conclusion
   tied to the scenario. Glance at the mark allocation: **[3]** wants ~3 distinct points.
""")

c1, c2 = st.columns(2)
with c1:
    st.info("**Time budget** — CS1A: 100 marks in 200 min ⇒ **~2 min/mark**. "
            "CS1B: ~100 marks in 110 min. If a part is overrunning its mark budget, "
            "write your conclusion and move on — come back if time allows.")
with c2:
    st.warning("**The four marks examiners say candidates throw away:** (1) no conclusion "
               "*in context*; (2) reciting bookwork instead of applying it; (3) R output left "
               "un-commented; (4) answering a different question than the one asked.")

st.divider()
st.subheader("Answer skeletons by topic")
st.caption("Open the one you need — these are the structures that win full marks.")

with st.expander("Hypothesis testing — the skeleton that never changes"):
    st.markdown("""
**State H₀/H₁ → test statistic → its distribution → critical value or p-value → decision → conclusion *in context*.**
A bare "reject H₀" loses the context mark every single time.

- **Test chooser:** one mean → *t*-test; two means → two-sample / paired *t*; equality of
  variances → *F*-test; goodness-of-fit / association → *χ²* (association df = (r−1)(c−1)).
- **Type I = innocent convicted** (reject true H₀); **Type II = guilty walks free**
  (fail to reject false H₀). **Power = 1 − β** = catching the guilty.
- p-value sentence: *"p = 0.03 < 0.05, so we reject H₀ at the 5% level and conclude
  [the thing], in context."*
""")

with st.expander("MLE — the 'L-L-D-S-S' recipe"):
    st.markdown("""
Write **L**ikelihood → take **L**og → **D**ifferentiate → **S**et to 0 → **S**olve
(then check the 2nd derivative < 0 for a maximum).

- **MSE = variance + bias².** Unbiased ⇒ MSE is just the variance.
- MLE properties: **consistent, asymptotically Normal & efficient, invariant**
  (the MLE of g(θ) is g(θ̂)).
- Large-sample variance from **Fisher information**: Var(θ̂) ≈ 1/I(θ).
""")

with st.expander("Confidence intervals — pick the right pivot"):
    st.markdown("""
- Mean, σ **known → z**; σ **unknown → t**. Variance → **χ²** (and it's **asymmetric** —
  never write s² ± something).
- Interpretation examiners want: *"95% of such intervals would contain the true value"*,
  **not** "95% probability the parameter is in this one".
- Prediction interval (a single new observation) is **wider** than the CI for the mean response.
""")

with st.expander("Linear regression — 'LINE'"):
    st.markdown("""
Assumptions = **L**inearity, **I**ndependence, **N**ormality, **E**qual variance.

- Slope β̂₁ = S_xy/S_xx; line always passes through (x̄, ȳ). In simple regression **R² = r²**.
- Test the slope: t = β̂₁ / se(β̂₁), se(β̂₁) = √(σ̂²/S_xx), σ̂² = SSE/(n−2).
- **Prediction interval > confidence interval** (individual vs mean) — examined as a pair.
""")

with st.expander("GLMs — 'Random, Systematic, Link' (the heaviest dual-paper topic)"):
    st.markdown("""
Three components: the **response distribution** (exponential family), the **linear
predictor** η = Σβx, and the **link** g(μ) = η.

- **Canonical links:** Normal → identity, **Poisson → log**, **Binomial → logit**,
  Gamma → inverse. (Poisson-log and Binomial-logit are the exam favourites.)
- Predict: μ = g⁻¹(η). For log link μ = e^η; **exp(β)** is a **rate/odds ratio**.
- **Deviance vs AIC:** difference in deviance tests **nested** models (≈ χ² on Δparameters);
  **AIC compares any models, lower is better**. Don't mix these up.
""")

with st.expander("Bayesian & credibility"):
    st.markdown("""
**Posterior ∝ prior × likelihood.** Conjugate pairs: **Beta–Binomial, Gamma–Poisson,
Normal–Normal**.

- Bayes estimate by loss: **mean / median / mode** for **quadratic / absolute / 0–1** loss.
- **Credibility = Z·(data mean) + (1−Z)·(prior mean)**; Z rises with more data
  (Z = n/(n+k)). The posterior mean *is* a credibility estimate — the bridge examiners probe.
""")

with st.expander("Distributions & generating functions — choosing is half the marks"):
    st.markdown("""
- **Counts → Poisson** (Negative Binomial if over-dispersed); **waiting time → Exponential/Gamma**;
  **claim sizes → Gamma/Lognormal**; **proportions → Binomial/Beta**.
- **Poisson signature: mean = variance.** Variance ≫ mean ⇒ over-dispersion ⇒ Negative Binomial.
- **Continuity correction (±0.5)** whenever you approximate a discrete distribution by the Normal.
- **MGF** = moment machine (differentiate, set t=0). Sum of independents ⇒ **multiply MGFs**;
  same MGF ⇒ same distribution. **CGF = ln(MGF)**: 1st cumulant = mean, 2nd = variance.
""")

with st.expander("CS1B (R) — claw back the 40%"):
    st.markdown("""
The reports say it yearly: marks are lost on half-remembered syntax, un-commented output,
and answering the wrong thing — rarely on the statistics.

- **Always write one sentence interpreting the output** (the comment carries marks the
  number doesn't).
- **`sd`, not variance**, in `rnorm`/`dnorm` etc. (the most common silent R error).
- **`set.seed()` before any simulation** so results are reproducible.
- Core patterns to have automatic: `summary` / `mean` / `sd`, the `d/p/q/r` family,
  `t.test` / `var.test` / `chisq.test`, `lm()` + `predict`, `glm()` (Poisson & logistic)
  + `AIC` / `anova(..., test="Chisq")`, `cor.test`, `qqnorm`/`qqline`,
  simulation with `set.seed` + `replicate`.
- **Comment your code** (`# fit Poisson GLM`) — fewer errors, signals method to the marker.
""")

st.divider()
st.success("**Put it into practice:** open the **Study** page, choose the "
           "**Exam-style questions** deck, switch to **Deep (AI marking)**, and write a full "
           "answer from a blank page using the skeleton above. Then check it against the "
           "mark scheme shown on reveal.")
st.page_link("pages/1_📚_Study.py", label="▶ Practise exam-style questions", icon="📚")
