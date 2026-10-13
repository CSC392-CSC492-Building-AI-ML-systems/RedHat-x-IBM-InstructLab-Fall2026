# M3 Taxonomy Seeding
READ DOCS: [https://docs.instructlab.ai/taxonomy/](https://docs.instructlab.ai/taxonomy/)

EXAMPLE TAXONOMY: [https://github.com/instructlab/taxonomy](https://github.com/instructlab/taxonomy)

The InstructLab taxonomy: a tree of small YAML files that tells `ilab` what to teach the model.
InstructLab's teacher model expands our hand-written seeds into the synthetic training set, so **every mistake in a seed is copied thousands of times**. Quality over quantity.

## What is "Knowledge"?
TAKEN FROM: [https://docs.instructlab.ai/taxonomy/knowledge/](https://docs.instructlab.ai/taxonomy/knowledge/)

In the InstructLab world, knowledge consists of data and facts and is backed by documents. When you create knowledge for a model, you're giving it additional data to more accurately answer questions.

Knowledge contributions in this project contain a few things:

- A Markdown or PDF file in a git repository that holds your information. For example, these repositories can include Markdown or PDF versions of information on Oscar 2024 winners, Law books, Shakespeare, Sports, Chemistry, etc. Note that sources must be licensed using a compatible license. Learn more from our list of accepted sources.
- A qna.yaml file that asks and answers questions about the information in the git repository.
- An attribution.txt file that includes the sources for the information used in the qna.yaml. Note that this file is not required if you are not submitting to the upstream taxonomy repository at https://github.com/instructlab/taxonomy.


### Layout of taxonomy/
The taxonomy draws from a separate knowledge-docs directory (documentation says repo)
```
knowledge-docs/
        either
    liu-theory-of-computation.pdf
        OR
    induction.md
    recurrences.md, etc. etc.

taxonomy/
    knowledge/computer_science/csc236/
        induction/            qna.yaml  attribution.txt
        recurrences/          qna.yaml  attribution.txt
        program_correctness/  qna.yaml  attribution.txt
        regex_languages/      qna.yaml  attribution.txt
        dfa_nfa/              qna.yaml  attribution.txt
    compositional_skills/
        ...
    foundational_skills/
        ...
```
All of the "ground truth" knowledge & facts to teach the model are in the `knowledge/` branch of the taxonomy tree, which draws from the knowledge docs. Each topic has its own "leaf" folder containing a `qna.yaml` which contains topic-related questions and answers.

Teaching the model specific ways to grade comes in the skills folders.  
For now, don't worry about the skills part. Let's get started on the topics.

## Source documents

Every knowledge entry requires two things: a source Markdown file (.md) and a qna.yaml file. The YAML contains training examples grounded in the source document; it does not replace the source document.

For now, we slap in the course notes PDF in the `knowledge-docs/` directory. 

There may be issues with notation getting jumbled up, but for simplicity, let's proceed like this. See footnote for consideration of manually writing markdown files.

## Knowledge entry

Reference: [https://docs.instructlab.ai/taxonomy/knowledge/file_structure/](https://docs.instructlab.ai/taxonomy/knowledge/file_structure/)

### Writing `qna.yaml`

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

**Rules of thumb**
- Contexts must be copied from the source files in `data/sources/`, because generation checks them against the documents. Do not paraphrase them.
  - NOTE: This works better if our source docs are manually written markdown files. See footnotes. But for now, I guess we can rip from the course notes.
- Questions should be answerable from their context alone and should not be near-duplicates.
- Cover the topic broadly: definitions, a worked example, a common mistake, a proof technique.
- Use `|` block scalars for multi-line text, and `$...$` for inline math. Write `\\` carefully in
  LaTeX; plain backslashes inside double-quoted YAML strings must be escaped.

### Writing `attribution.txt`

Right next to each `qna.yaml` file. 

```
Title of work: CSC236 tutorial solutions
Link to work: <course page or repo link>
License of the work: Course material used with permission of <professor name> on <date>
Creator names: <instructors / TAs who wrote it>
```


## Footnote on reference documents
Hypothetically, we could just use the David Liu course notes, since InstructLab allows PDFs. But I'm afraid that InstructLab will not read the mathematical notation correctly. If it does not work properly, we'd have to compile a markdown ourselves.

In the case that we don't simply slap in the course notes, we manually create a source markdown file (`data/sources/csc236/<topic>/*.md`)

    Write a concise reference document covering the theory you want the model to learn. This is the underlying course material and NOT a list of questions and answers. Include definitions, theorems, proof techniques, worked examples, and common mistakes for your topic. Use mathematical notation and make sure statements and proofs are correct.

    To make things easier you don't have to write the material yourself; you can adapt course notes (e.g. David Liu course notes that Josh can provide). You can also use an LLM to scan and skeleton relevant sections of the course notes, but a HUMAN must verify correctness and notation.  