# rubrics

The grading rubrics, one file per assignment question. Each rubric lists the criteria, the points for each, and what earns full, partial, minimal or no credit.

## This week's ownership

Ray leads the rubric work. This is a separate workstream from writing topic knowledge entries.

The rubric lead should:

- decide and document the rubric file format before adding question rubrics;
- create one rubric per selected assignment question, with criteria, points, and descriptions of full, partial, minimal, and no credit;
- coordinate with the test-set authors so each test answer is graded against the rubric for its question.

Ray also contributes to the ethics documents, with Sungmin (also called Ashton) leading that work. Josh and Nikita own multiple knowledge topics, while Daniel owns one topic alongside cluster and InstructLab setup; see [taxonomy/README.md](../taxonomy/README.md).

The model grades against these files, so once test answers have been written against a rubric, don't change it without updating and rechecking the affected test answers. Part of milestone 1.

## Rubric
rubric_induction_v1.json contains a minimal induction problem rubric for our usage.

Usage: The same induction rubric can be used in different types of problem examples. It is the job of the problem example to connect a specific class of problem (e.g. sum proof vs divisibility proof) to the abstracted induction proof structure. 

Note on YAML: Writing a vertical bar (|) before a multiline string tells YAML to treat it as a single multiline string. This allows the use of colons in a rubric. 

Note on grading output format: This should probably be checked.