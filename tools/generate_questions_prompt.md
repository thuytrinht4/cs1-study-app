# Free question generation with Claude Code (your Max plan)

Generating questions is the most expensive AI call in the app (~2¢ each on the API).
Your **Claude Max plan** can do it for free in VS Code. Use this whenever you want
a fresh batch of practice questions — there's no limit that matters for your usage.

## Steps
1. Open the `cs1-study-app` folder in VS Code.
2. Open Claude Code (model: **Sonnet** is plenty; Opus if you want the toughest questions).
3. Paste the prompt below (edit the count/topics as you like).
4. When it's done, in the VS Code terminal run:
   ```
   python tools/validate_exam_cards.py
   ```
   Fix anything it flags (ask Claude Code to correct it), until it reports
   **0 error(s)** / "All valid".
5. Open the app → **Home → "Import / update exam questions"**. Your new questions
   are now studyable (and AI-markable with cheap Haiku) and appear in mock exams.
6. If your app is deployed: commit & push so the new `data/exam_cards_3.json` goes live.

## The prompt to paste into Claude Code

> Generate **15** new IFoA **CS1** exam-style questions and **append** them to
> `data/exam_cards_3.json` (create the file as a JSON array if it doesn't exist;
> otherwise load it, append, and save — do not overwrite existing entries).
>
> Match the schema used in `data/exam_cards.json` exactly. Each question object needs:
> `id`, `topic`, `module` (int 1–5), `type` ("concept" | "formula" | "r"), `front`,
> `model_answer`, `mark_scheme` (a list of `{ "point": "...", "marks": n }`), and
> `max_marks`. Use unique ids like `gen_g01`, `gen_g02`, … that don't clash with any
> id already present in `data/exam_cards*.json`.
>
> Requirements for quality:
> - **Weighting:** ~6 on GLMs (4.2), 3 on hypothesis testing (3.3), 2 on linear
>   regression (4.1), 2 on MLE/estimation (3.1), 1 on Bayesian (5.1), 1 on
>   credibility (5.2). (Adjust if I ask for specific topics.)
> - **Style:** multi-part, applied, past-paper feel; parts labelled (i), (ii), …
>   with the marks shown inline as **[n]**.
> - **Model answer:** start with the method/approach, then a fully worked solution
>   with clear substitution, ending with interpretation in context. Reward the exam
>   style examiners want: state H₀/H₁, conclude in context, comment on R output.
> - **Mark scheme:** point-by-point; the `marks` must **sum exactly to `max_marks`**.
> - **R/CS1B questions:** set `type: "r"` and put correct R in fenced ```r code blocks.
> - Make every calculation numerically correct. Use realistic numbers/scenarios.
>
> After saving, run `python tools/validate_exam_cards.py` and fix any errors it
> reports until it passes with zero errors. Then tell me how many you added and the
> new total.

## Tips
- Ask for a focused batch when you spot a weakness: *"…generate 8 questions, all on
  GLMs (4.2), mixing Poisson and logistic, two of them R/CS1B."*
- Re-run any time. The validator + unique-id rule keep the bank clean.
- This keeps your only real API cost (generation) at **$0**, leaving just the
  pennies-per-answer Haiku marking inside the app.
