"""Make a copy of ilab's data generation pipeline that keeps our rubrics exactly as written.

ilab's skills pipeline starts by asking the teacher to write 10 new versions of
each seed example's context. For our grading skills the context is the question
and its rubric, so every generated example ends up with a rubric the teacher
made up. This copy skips that step: each seed's own question and rubric are used
unchanged, and the teacher only writes new student answers and grades them.
Every other step is ilab's own.

Three optional changes, all recommended for the grading skills:
  --strict-grading      Use a copy of ilab's response prompt with extra rules that tell the
                        teacher to give credit only for what the student answer actually
                        writes, keep the arithmetic consistent, and grade once.
  --varied-answers      Use a copy of ilab's question prompt that says each "question" is a
                        student answer, forbids copying the question or rubric into it, and
                        asks for mostly flawed answers (about one in five fully correct).
                        Without it the teacher writes mostly correct answers.
  --skip-question-eval  Remove ilab's question check. It judges "questions" with a generic
                        prompt that wants them 1 to 2 sentences long, so it throws away
                        multi-line student proofs. The filter script checks rows instead.

Run in the ilab environment, from the repo folder:
    python3 tools/make_fixed_rubric_pipeline.py --strict-grading --varied-answers --skip-question-eval \
        "$PWD/pipelines/fixed_rubric"
Then give the folder to ilab with --pipeline, using an absolute path:
    GEN_ARGS="--pipeline $PWD/pipelines/fixed_rubric" sbatch jobs/generate_data.sh \
        compositional_skills/grounded/grading/csc236/regex

Use this pipeline only for the grading folders. It also freezes the contexts of
any other grounded skill, such as proof structure, so run those with ilab's
normal pipeline (--pipeline full) in a separate job.

SCALE (ilab's --sdg-scale-factor) sets how many times the teacher is asked for
new student answers for each seed example, and it writes 3 each time. ilab's own
pipeline makes 10 new contexts per seed, so SCALE=10 gives about the same amount
of data as before.
"""
import argparse
from pathlib import Path

import instructlab.sdg
import yaml

STRICT_RULES = """\
* Grade strictly against the rubric in the context. Give a criterion a level only if the
  student answer explicitly contains what that level requires.
* If a required statement, step or justification is missing from the student answer, choose
  the lower level. Never treat a missing step as "implicit" or "clear".
* Each criterion's points must equal the points of the chosen level, and the Total and the
  Grade must both equal the sum of the criterion points.
* If the student answer is empty or missing, give every criterion the level "none".
* Write the grade once. Do not revise it, add corrections or give a second version.
"""

ANSWER_RULES = """\
* Here each "question" is a student's answer to the question in the context, written the way a
  student would write it, starting with "Student Answer:". Return only the student answer, with
  no grade or feedback.
* Never copy the context, the question or the rubric into a student answer.
* Vary the quality of the answers: about one in five should be fully correct, and the others
  should contain one or more of the mistakes that the rubric's partial, minimal and none levels
  describe. Make each answer different from the example and from the others.
"""
REPLACED_LINE = "* Simply return the questions, do not return any answers or explanations.\n"

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("folder", help="where to write the pipeline (use an absolute path with ilab)")
parser.add_argument("--strict-grading", action="store_true", help="use the stricter response prompt")
parser.add_argument("--varied-answers", action="store_true", help="use the student-answer question prompt")
parser.add_argument("--skip-question-eval", action="store_true", help="remove ilab's question check")
args = parser.parse_args()

full = Path(instructlab.sdg.__file__).parent / "pipelines" / "full"
out = Path(args.folder).resolve()
out.mkdir(parents=True, exist_ok=True)

# ilab needs all three pipeline files in the folder, even though we only change one.
for name in ("knowledge.yaml", "freeform_skills.yaml", "grounded_skills.yaml"):
    pipeline = yaml.safe_load((full / name).read_text())
    for block in pipeline["blocks"]:
        # Each step names its prompt file relative to ilab's own folder, which
        # doesn't work from a new folder, so point to ilab's prompt files directly.
        config = block.get("config", {})
        if "config_path" in config:
            config["config_path"] = str((full / config["config_path"]).resolve())

    if name == "grounded_skills.yaml":
        blocks = pipeline["blocks"]
        names = [b["name"] for b in blocks]
        assert names[:2] == ["gen_contexts", "gen_grounded_questions"], names
        # Instead of asking the teacher for new contexts, copy each seed's own
        # context (question and rubric) into the column the next steps read.
        blocks[0] = {
            "name": "keep_seed_context",
            "type": "DuplicateColumnsBlock",
            "config": {"columns_map": {"seed_context": "context"}},
        }
        # Ask for new student answers SCALE times per seed, with the same
        # settings ilab used to ask for new contexts.
        blocks[1]["config"]["gen_kwargs"] = {"temperature": 0.7, "n": "scaled", "seed": 42}

        if args.varied_answers:
            questions = blocks[1]
            prompt = yaml.safe_load(Path(questions["config"]["config_path"]).read_text())
            assert REPLACED_LINE in prompt["principles"], "ilab's question prompt changed; update ANSWER_RULES placement"
            prompt["principles"] = prompt["principles"].replace(REPLACED_LINE, ANSWER_RULES)
            answers_path = out / "grounded_questions_student_answers.yaml"
            answers_path.write_text(yaml.safe_dump(prompt, sort_keys=False, width=4096))
            questions["config"]["config_path"] = str(answers_path)

        if args.skip_question_eval:
            blocks[:] = [b for b in blocks if b["name"] not in ("eval_grounded_questions", "filter_grounded_questions")]
            # The removed filter step also dropped this helper column; drop it after use instead.
            blocks[1]["drop_columns"] = ["num_samples"]

        if args.strict_grading:
            responses = next(b for b in blocks if b["name"] == "gen_grounded_responses")
            prompt = yaml.safe_load(Path(responses["config"]["config_path"]).read_text())
            marker = "* Return the response between [Start of Response] and [End of Response] tags.\n"
            assert marker in prompt["principles"], "ilab's response prompt changed; update STRICT_RULES placement"
            prompt["principles"] = prompt["principles"].replace(marker, STRICT_RULES + marker)
            strict_path = out / "grounded_responses_strict.yaml"
            strict_path.write_text(yaml.safe_dump(prompt, sort_keys=False, width=4096))
            responses["config"]["config_path"] = str(strict_path)

    (out / name).write_text(yaml.safe_dump(pipeline, sort_keys=False))

steps = [b["name"] for b in yaml.safe_load((out / "grounded_skills.yaml").read_text())["blocks"]]
print(f"Wrote the pipeline to {out}")
print("Grounded skills steps: " + " -> ".join(steps))
