# taxonomy/

The InstructLab taxonomy: a tree of small YAML files that tells `ilab` what to teach the model.
InstructLab's teacher model expands our hand-written seeds into the synthetic training set, so
**every mistake in a seed is copied thousands of times**. Quality over quantity.

## Layout

```
taxonomy/
  knowledge/computer_science/csc236/
    induction/            qna.yaml  attribution.txt
    recurrences/          qna.yaml  attribution.txt
    program_correctness/  qna.yaml  attribution.txt
    regex_languages/      qna.yaml  attribution.txt
    dfa_nfa/              qna.yaml  attribution.txt
  compositional_skills/grading/csc236/proof_grading/
                          qna.yaml  attribution.txt     <- GENERATED, never hand-edited
```

- Each leaf folder holds exactly one file named `qna.yaml` (the name matters) plus `attribution.txt`.
- **Knowledge** entries teach CSC236 content and cite source documents. **Skill** entries teach the
  grading behavior and have no source documents.
- We use **one** grading skill entry for all topics, because InstructLab needs a minimum number of
  seeds per entry (about 5 at the time of writing) and each person only writes about 3.

## Who owns what

| Person | Topic (knowledge entry) | Skill seeds (in `data/examples/`) |
|---|---|---|
| Josh | `induction` | 3 or more, topic `induction` |
| Daniel | `recurrences` | 3 or more, topic `recurrences` |
| Ray | `program_correctness` | 3 or more, topic `program_correctness` |
| Nikita | `regex_languages` | 3 or more, topic `regex_languages` |
| Ashton | `dfa_nfa` | 3 or more, topic `dfa_nfa` (lighter if the ethics doc is crunching) |

Josh is also **taxonomy owner**: he merges PRs, regenerates the skill file, and runs `ilab taxonomy diff`.

## Knowledge entry: how to write one

Copy this template to `taxonomy/knowledge/computer_science/csc236/<topic>/qna.yaml`:

```yaml
version: 3
created_by: <your-github-username>
domain: computer_science
document_outline: |
  One or two sentences: what this topic covers and which course documents are used.
seed_examples:
  - context: |
      A passage copied from the source markdown (keep it short, well under 500 tokens).
    questions_and_answers:
      - question: A question the passage answers.
        answer: A complete, correct answer grounded in the passage.
      - question: ...
        answer: ...
      - question: ...
        answer: ...
  # repeat for 5 contexts total, each with 3 question/answer pairs
document:
  repo: https://github.com/<org>/<repo>      # must contain the markdown at the commit below
  commit: <40-character commit SHA>
  patterns:
    - data/sources/csc236/<topic>/*.md
```

Rules of thumb:

- Contexts must be copied from the source files in `data/sources/`, because generation checks them
  against the documents. Do not paraphrase them.
- Questions should be answerable from their context alone and should not be near-duplicates.
- Cover the topic broadly: definitions, a worked example, a common mistake, a proof technique.
- Use `|` block scalars for multi-line text, and `$...$` for inline math. Write `\\` carefully in
  LaTeX; plain backslashes inside double-quoted YAML strings must be escaped.
- Commit and push the source markdown **first**, then put that commit SHA in `commit:`. When you
  change the sources, update the SHA.

### `attribution.txt` (required for knowledge entries)

```
Title of work: CSC236 tutorial solutions
Link to work: <course page or repo link>
License of the work: Course material used with permission of <professor name> on <date>
Creator names: <instructors / TAs who wrote it>
```

If permission has not been given, **do not commit the entry**. Keep it local and tell the group.

## Skill entry: the grading skill

Do not edit `qna.yaml` here by hand. It is built from validated examples:

```bash
GITHUB_USER=<name> python3 tools/make_seed.py data/examples/*.json \
  > taxonomy/compositional_skills/grading/csc236/proof_grading/qna.yaml
```

`make_seed.py` refuses to run if any example fails the validator, and it uses the same prompt
template as evaluation, so training and testing match. `attribution.txt` for the skill:

```
Title of work: GradeAI grading seed examples
Link to work: <our repo>
License of the work: CC-BY-SA-4.0 (written by the team)
Creator names: Daniel Halpern, Gerardus Raynard Effrien, Nikita Nathania Rudy, Sungmin Cho, Josh Villas
```

## Size limits (check these in the first hour)

InstructLab limits how long seed examples can be (at the time of writing: roughly 500 tokens per
knowledge context, and about 750 words for question + context + answer in a skill seed). Our worked
example is about 320 words with the compact rubric, so we have room, but **a rubric with 6 verbose
criteria may not fit**. Keep rubric descriptions to one short sentence. Limits and minimums change
between ilab versions: run `ilab taxonomy diff` on a one-seed test entry and read the error messages.

## Does `ilab` accept `taxonomy/` inside our repo? (Daniel, Day 1)

`ilab taxonomy diff` and `ilab data generate` detect your new entries by comparing the taxonomy
folder against a git base. ilab expects the taxonomy path to be a git repository, and ours is a
subfolder of the project repo. Test this first:

```bash
ilab config init                      # set the taxonomy path to <repo>/taxonomy
ilab taxonomy diff
```

If it complains, either make `taxonomy/` its own git repository (or submodule), or keep a separate
clone for ilab and sync it from this folder with a script. Document the decision in `env/README.md`.

## Review cycle (one pull request per person)

Josh reviews Daniel, Daniel reviews Ray, Ray reviews Nikita, Nikita reviews Ashton, Ashton reviews Josh.
The reviewer checks:

1. `python3 tools/validate.py data/examples/*.json` passes.
2. Grades match how a TA would grade (re-grade blind, then compare).
3. All four levels, a typo case, and a word-salad case are present for that topic.
4. Different rubric shapes across examples (see `rubrics/README.md`).
5. Knowledge contexts match the source files and the answers are correct.
6. No question appears in `test_set/QUESTION_LEDGER.md`.

## Definition of done for M3

- [ ] 5 knowledge entries (minimum 3) with attribution and pushed source commit
- [ ] Skill entry generated from 15 or more validated examples covering all four levels
- [ ] `ilab taxonomy diff` passes with no errors
- [ ] All question ids added to `test_set/QUESTION_LEDGER.md`
- [ ] All five members have reviewed one teammate's work