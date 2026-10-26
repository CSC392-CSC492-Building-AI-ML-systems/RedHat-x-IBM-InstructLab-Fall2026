# Compositional Skills
Background info on the topic.

Compositional skills are intended for teaching a model to perform a task. This section is **performative**; that is, the emphasis is on what the model does rather than what it knows.

Examples: Extract assumptions and conclusion from a user-supplied proof.
- TODO: Make this an actual skill lol 

Compositional skills are further divided into grounded and ungrounded skills:

## Grounded: Requires context
A grounded skill teaches the model how to perform a task using information supplied by the user, rather than relying on the model's existing knowledge.

Example: Extract information from a meeting transcript.

```
version: 2
task_description: Extract action items from a meeting transcript.
created_by: your_username

seed_examples:
  - context: |
      Alice: Bob will finish the database migration by Friday.
      Bob: I will also write the deployment documentation.
    question: What are Bob's action items?
    answer: |
      1. Finish the database migration by Friday.
      2. Write the deployment documentation.
```

## Ungrounded: Does not require context
Teaches a model to perform a task without requiring a separate context field.

Example: 
```
version: 2
task_description: Write a haiku about a specified topic.
created_by: your_username

seed_examples:
  - question: Write a haiku about winter.
    answer: |
      Snow blankets the earth
      Bare branches reach for the gray sky
      Spring sleeps underground
```