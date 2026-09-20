# PORTABLE_PACKAGE_EVAL_RUNTIME_01

Status: IMPLEMENTATION_CANDIDATE
Scope: AIOS-Tools / portable tool-package evaluation
Authority transfer: false

## Purpose

Make clean-room behavioral regression a first-class step when AIOS builds or revises a portable tool package.

The evaluator must answer two different questions without conflating them:

1. Does attaching the package improve behavior relative to the same task without the package?
2. Does the package behave correctly inside the real ChatGPT product surface?

## Core execution model

```text
package checkpoint
  -> exact artifact SHA-256
  -> frozen evaluation fixture
  -> paired PACKAGE_OFF / PACKAGE_ON requests
  -> deterministic contract grading
  -> optional semantic/model grading
  -> regression comparison
  -> product-surface acceptance plan
  -> release gate evidence
```

The two paired requests preserve task, allowed tools, provider/model selection, storage posture, and research policy. The only package-treatment delta is the package attachment plus its package-entry instruction.

## Clean-room law

For the automated lane, the package-eval request declares:

- no memory;
- no custom instructions;
- no plugins;
- no project context;
- no prior chat context;
- explicit tools only;
- `store: false`.

This is a behavioral-isolation contract. It does not imply that the provider has no independent safety processing.

## Product-surface acceptance

Major package releases may require a real ChatGPT acceptance pass using an Unpersonalized Temporary Chat. Current ChatGPT documentation states that this mode does not use memory, custom instructions, or plugins. Product-surface acceptance remains separate from API/stateless regression because the UI, file attachment, browser, and product routing are part of what is being tested.

If authentication, CAPTCHA, or a supported site challenge blocks the product-surface run, the browser may enter a governed human-takeover state. Secret input must remain model-invisible. Automation may resume only after exact-origin/session revalidation.

Product-surface execution state remains `NOT_EXECUTED` until the real product run produces evidence.

## First implementation slice

This slice provides:

- typed fixture contract;
- exact artifact and fixture SHA-256;
- paired PACKAGE_OFF / PACKAGE_ON capsule compilation;
- deterministic string/ordering/regex/length grading;
- package-on/off result comparison;
- ChatGPT product-surface acceptance manifest with human-takeover states;
- standalone `aios-package-eval` CLI;
- negative-path tests.

This slice does not call a model, launch ChatGPT, solve CAPTCHA, or claim semantic grading. Those are later adapters consuming the same capsule contract.

## Evidence and release relationship

`CHECKPOINT != EVAL PASS != RELEASE != CANON`.

A package build checkpoint is input identity. A clean-room regression run is behavioral evidence. A product-surface smoke test is UI/runtime evidence. Release promotion remains separately governed.

## External implementation evidence

- OpenAI Temporary Chat documentation: https://help.openai.com/en/articles/8914046-temporary-chat-in-chatgpt
- OpenAI Cloud Browser documentation: https://help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt
- OpenAI Responses API reference: https://developers.openai.com/api/reference/cli/resources/responses/methods/create
- OpenAI Evals API reference: https://developers.openai.com/api/reference/java/resources/evals/methods/create
- OpenAI grader models reference: https://developers.openai.com/api/reference/ruby/resources/graders/subresources/grader_models

These sources describe current provider/product capabilities. They do not transfer architecture authority to external documentation.
