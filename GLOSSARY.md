# MCP – Indirect Prompt Injection

A benchmark that measures how vulnerable LLM agents are to indirect prompt injection when they use tools over MCP. Its design and vocabulary follow AgentDojo.

## Language

### Threat

**Indirect prompt injection**:
An attack where the attacker's instructions reach the model only through data returned by tools, never through the system or user prompt.
_Avoid_: Prompt injection (unqualified), direct prompt injection

**Attack**:
A strategy that turns an injection task's goal, and for some attacks the names of the tools its reference solution uses, into text and places it into injection vectors.
_Avoid_: Injection technique, template, jailbreak

**Attack text**:
The text an attack produces from one injection task's goal and places into injection vectors.
_Avoid_: Payload, injection (for the text), prompt

**Attack family**:
What an attack forges to make the model follow the goal: nothing, the conversation boundary, the goal's link to the task, or the source of the instruction. The experiment's attacks are all of different families.
_Avoid_: Attack type, attack kind, attack class

**Defense**:
A change to the agent pipeline meant to stop attacks, such as `spotlighting`, `sanitizer`, `tool-filter` or `security-policy`; spelled "defense", as in AgentDojo.
_Avoid_: Defence, guardrail, mitigation, protection

**Delimiter**:
Text a defense puts around tool results for the model to see, such as spotlighting's `<TOOL_RESULT>` and `</TOOL_RESULT>`; it is part of the defense, fixed in code, and is not a placeholder.
_Avoid_: Marker (alone), tag, placeholder

### Task suite

**Suite**:
A bundle of things that belong together and are used as one; in this project, always short for task suite.
_Avoid_: Benchmark, dataset

**Task suite**:
A complete setup that bundles everything needed to evaluate an agent: environment, MCP tools, injection vectors, user tasks and injection tasks.
_Avoid_: Suite of tests, benchmark, scenario, use case

**Environment**:
The simulated world an agent works in: its initial state, reset to a fresh copy for every run.
_Avoid_: Initial state, environment state, world

**Component**:
One part of the environment's state, such as `inbox`, `calendar`, `cloud_drive`, `web` or `jira`.
_Avoid_: Domain (when meaning the data), module

**Domain**:
The kind of application a component represents, such as `email`, `calendar`, `cloud_storage`, `web` or `issue_tracking`.
_Avoid_: Application area, suite, scenario

**Source domain**:
The domain of the injection vector that carries the attack: where the agent reads the attacker's text.
_Avoid_: Source (alone), vector, channel

**Target domain**:
The domain where an injection task's goal is carried out: where the attacker wants the agent to act.
_Avoid_: Target (alone), goal domain, injection target

**MCP tool**:
A function the agent calls over MCP to read or change the environment; tool results are the only channel an attack reaches the model through.
_Avoid_: Function, tool call (for the tool itself)

**MCP server**:
One of five servers, one per domain, that exposes that domain's MCP tools and works only on its component.
_Avoid_: Server (alone, when the model API is meant), backend, service

**Injection vector**:
A named place in the environment's data where an attack can be inserted, with a benign default when no attack runs.
_Avoid_: Injection slot, injection placeholder, attack carrier

**Tool result format**:
How a tool result carries the text it returns: **raw** when the result is the text itself (a web page, a file's content), **structured** when the text is a field of a serialized record (an email's body, an event's description).
_Avoid_: Vector format, output type, YAML vector

**Placeholder**:
The `{@inject:<vector_id>}` mark in environment data where an injection vector's text is filled in before a run; the `@` sets it apart from the `str.format` fields (`{goal}`, `{user}`, `{model}`, `{tools}`) of attack templates. The model never sees a placeholder.
_Avoid_: Marker, tag, template field (for `{@inject:…}`)

### Tasks

**Task**:
One specific thing the agent can be made to do in the environment, together with a check whether it was done; either a user task or an injection task.
_Avoid_: Job, goal (for the whole task), test

**User task**:
A legitimate task the user gives the agent, with a reference solution and a check that it was solved.
_Avoid_: Task (when a user task specifically is meant), prompt, case

**Injection task**:
The attacker's goal, with a reference solution and a check that the agent carried it out.
_Avoid_: Injection target, attacker task, dangerous action

**Ground truth**:
The reference sequence of tool calls that solves a user task or achieves an injection task's goal.
_Avoid_: Expected calls, reference solution (in code)

### Evaluation

**Agent**:
A model driven in a loop where it can call MCP tools until it gives a final answer.
_Avoid_: Model (when tool use is meant), assistant

**Agent pipeline**:
The ordered list of pipeline elements that makes up an agent; a defense fills its hooks.
_Avoid_: Agent loop, chain, harness

**Hook**:
A generic point of the agent pipeline where a defense plugs in one function: on each tool result, on each tool call before it runs, or on the tool list before the first model call. Unset, it keeps the baseline.
_Avoid_: Callback, slot, extension point

**Pipeline element**:
One step of the agent pipeline that takes the run's state (query, MCP runtime, messages, extra args) and returns it, possibly changed; it reaches the environment only through MCP tools.
_Avoid_: Stage, middleware, hook

**Baseline**:
The agent pipeline without any defense.
_Avoid_: No defense, vanilla, default pipeline

**Pipeline name**:
The name of one model × defense combination: `<model>` for the baseline, `<model>-<defense>` otherwise.
_Avoid_: Config name, agent name

**Configuration**:
One model × defense × attack combination.
_Avoid_: Setting, cell, setup

**Run**:
One execution of an agent on one user task, from the prompt to the final answer, possibly through many tool calls; either without an attack or with one injection task and one attack.
_Avoid_: Case, trial, episode

**Run spec**:
The description of one run: model, defense and task, plus an injection task and an attack for a security run; enough to give the run's file path without running it.
_Avoid_: Job, run config

**Final answer**:
The agent's last message without tool calls; what `utility` and `security` get as `model_output`.
_Avoid_: Response, output (alone), completion

**Run type**:
One of the four kinds of runs in the experiment: utility run, security run, injection task check or subset validation.
_Avoid_: Mode, experiment type

**Utility run**:
A run of one user task with no attack, injection vectors at their benign defaults.
_Avoid_: Benign run, clean run, no-attack run

**Security run**:
A run of one user task with one injection task and one attack.
_Avoid_: Attack run, security case, injection run

**Injection task check**:
A run where an injection task's goal is given to the agent as a normal user prompt, with no attack; shows whether the model can carry out the goal at all.
_Avoid_: Injection task as user task, capability check

**Pair**:
One user task together with one injection task, the unit a security run is built on.
_Avoid_: Case, combination, security case

**Balanced subset**:
The fixed 250 pairs used for every configuration, chosen so each injection task and every source × target domain combination is covered evenly.
_Avoid_: Sample, subsample, random subset

**Compatible pair**:
A pair whose target domain is not email and differs from its source domain, so the injection task's changes lie outside what the user task's check requires unchanged and both tasks can succeed in one run.
_Avoid_: Clean pair, independent pair

**Capable pair**:
A pair whose injection task the model achieved in its injection task check, so the model can carry out the goal at all; a pair is capable for one model, not in general.
_Avoid_: Achievable pair, feasible pair

**Exposed run**:
A security run where the attack text appears verbatim in a tool result the model saw, after any defense changed that result.
_Avoid_: Triggered run, reached run, injected run

**Silent compromise**:
A security run where utility and security are both true: the attack succeeded and the user task was still solved, so the user sees nothing wrong. It can only happen in a compatible pair.
_Avoid_: Stealthy attack, unnoticed attack

**Hijacked run**:
A security run where security is true and utility is false: the attack succeeded and the user task was not solved.
_Avoid_: Compromised run (covers silent compromise too)

**Disrupted run**:
A security run where utility and security are both false: the attack failed, and the user task was not solved either.
_Avoid_: Derailed run, denial of service

**Robust run**:
A security run where utility is true and security is false: the user task was solved and the attack failed.
_Avoid_: Safe run, clean run

**Subset validation**:
Security runs over all pairs for one configuration, to show that the balanced subset does not bias the result.
_Avoid_: Full run, cross-product run

**Utility**:
Whether the agent solved the user task.
_Avoid_: Task success, TSR

**Security**:
Whether the agent carried out the injection task's goal; true means the attack succeeded, which is bad.
_Avoid_: Attack success, safety

**Utility under attack**:
Utility measured on security runs: whether the agent still solved the user task while being attacked. It includes the effect of the attacker's own changes, so a successful injection outside a compatible pair makes it false.
_Avoid_: Robust utility, attacked utility

**ASR**:
Attack success rate: the share of security runs where security is true.
_Avoid_: Attack success, security rate, TSR

### Running

**Run file**:
The JSON file that records one run (messages, utility, security, error …); the source of truth for all metrics.
_Avoid_: Log, trace, result (alone)

**Sweep**:
A YAML file that describes a whole experiment (models, defenses, attacks, run types) and is expanded into individual runs.
_Avoid_: Batch, grid, experiment config

**Pilot**:
A small sweep run before the main one to catch bugs, written to its own directory.
_Avoid_: Smoke test, dry run

**Iteration limit**:
The maximum number of tool-calling rounds in one run; hitting it is agent behaviour, and the run is scored normally.
_Avoid_: Timeout, max steps

**Run error**:
An exception raised during the agent run that ends the run: an infrastructure error or a bug in the agent or defense code. It is recorded as `"<ExceptionType>: <message>"` so the two can be told apart; such runs are retried and excluded from metrics. A bug in the suite (environment, checks) is not a run error: it stops the command.
_Avoid_: Failure (alone), crash, error (when the agent's tool errors are meant)

**Infrastructure error**:
A run error outside the agent's control (API error, timeout, rate limit, a model reply with neither text nor tool calls, a completion without choices).
_Avoid_: Run error (when a bug in a defense may be meant)
