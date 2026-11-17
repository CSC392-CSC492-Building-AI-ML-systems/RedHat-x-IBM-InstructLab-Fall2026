import type { CourseSettings, Rubric } from './types'

export const DEFAULT_SETTINGS: CourseSettings = {
  code: 'CSC236H5 2026',
  name: 'Introduction to the Theory of Computation',
  term: 'Fall 2026',
  instructor: 'Prof. Mohammad Mahmoud',
  enrollment: 315,
  currentAssignment: 'Assignment 2',
  threshold: 70,
  autoApprove: true,
  requireSignoff: false,
  plagiarism: false,
  minutesPerManualGrade: 3,
  crowdmarkCourse: 'csc236-fall2026',
  institution: 'University of Toronto',
  roster: [],
  systemPrompt: 'You are GradeAI, a careful teaching assistant for CSC236 (Introduction to the Theory of Computation) at the University of Toronto. You grade student work strictly against the rubric you are given and reply with JSON only.',
  maxInputChars: 16000,
  updatedAt: 0,
}

/** Rubrics from the prototype. Used to seed a fresh course and in local mode. */
export const SEED_RUBRICS: Rubric[] = [
  {
    id: 'r1',
    name: 'A2 — Induction Proofs',
    assignment: 'Assignment 2',
    version: 'v1.3',
    createdBy: 'Prof. Mohammad Mahmoud',
    updatedAt: Date.UTC(2026, 8, 25),
    totalPoints: 40,
    criteria: [
      {
        name: 'Base Case',
        points: 10,
        description: 'Student correctly identifies and proves the base case.',
        levels: [
          { label: 'Full', points: 10, description: 'Base case proven correctly with all required details.' },
          { label: 'Partial', points: 6, description: 'Base case present but missing one element.' },
          { label: 'Minimal', points: 3, description: 'Attempt made but significant gaps.' },
          { label: 'None', points: 0, description: 'No base case or entirely incorrect.' },
        ],
      },
      {
        name: 'Inductive Hypothesis',
        points: 10,
        description: 'Correctly states what is assumed to hold for k.',
        levels: [
          { label: 'Full', points: 10, description: 'IH stated precisely and referenced in the inductive step.' },
          { label: 'Partial', points: 6, description: 'IH present but weakly stated or not properly used.' },
          { label: 'Minimal', points: 3, description: 'IH vague or confused with the conclusion.' },
          { label: 'None', points: 0, description: 'Missing or wrong.' },
        ],
      },
      {
        name: 'Inductive Step',
        points: 15,
        description: 'Proves the statement holds for k+1 assuming k.',
        levels: [
          { label: 'Full', points: 15, description: 'Step logically complete, algebra correct, references IH.' },
          { label: 'Partial', points: 9, description: 'Main idea correct but 1–2 algebraic or logic errors.' },
          { label: 'Minimal', points: 4, description: 'Idea present but significant errors in reasoning.' },
          { label: 'None', points: 0, description: 'Missing or wholly incorrect.' },
        ],
      },
      {
        name: 'Conclusion',
        points: 5,
        description: 'Final statement wrapping up the proof.',
        levels: [
          { label: 'Full', points: 5, description: 'Explicit conclusion referencing the original claim.' },
          { label: 'Partial', points: 3, description: 'Conclusion present but vague.' },
          { label: 'None', points: 0, description: 'No conclusion.' },
        ],
      },
    ],
  },
  {
    id: 'r2',
    name: 'A2 — Regular Languages',
    assignment: 'Assignment 2',
    version: 'v1.0',
    createdBy: 'Prof. Mohammad Mahmoud',
    updatedAt: Date.UTC(2026, 8, 20),
    totalPoints: 30,
    criteria: [
      {
        name: 'DFA Construction',
        points: 12,
        description: 'Correct DFA for the given language.',
        levels: [
          { label: 'Full', points: 12, description: 'DFA is correct and minimal.' },
          { label: 'Partial', points: 7, description: 'DFA correct for most strings but misses edge cases.' },
          { label: 'Minimal', points: 3, description: 'Fundamental structure present but significant errors.' },
          { label: 'None', points: 0, description: 'Incorrect.' },
        ],
      },
      {
        name: 'Closure Proof',
        points: 10,
        description: 'Proves closure under a given operation.',
        levels: [
          { label: 'Full', points: 10, description: 'Complete and rigorous.' },
          { label: 'Partial', points: 6, description: 'Mostly correct with minor gaps.' },
          { label: 'Minimal', points: 2, description: 'Shows understanding but proof is incomplete.' },
          { label: 'None', points: 0, description: 'Missing.' },
        ],
      },
      {
        name: 'Pumping Lemma',
        points: 8,
        description: 'Applies the pumping lemma correctly.',
        levels: [
          { label: 'Full', points: 8, description: 'Correct choice of s, decomposition, and contradiction.' },
          { label: 'Partial', points: 5, description: 'Correct approach but one case missing.' },
          { label: 'Minimal', points: 2, description: 'Attempt with major flaws.' },
          { label: 'None', points: 0, description: 'Incorrect.' },
        ],
      },
    ],
  },
]
