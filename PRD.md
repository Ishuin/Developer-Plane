\## The Core Philosophy: The Context Fabric



This project is not a traditional project manager or a simple dashboard. It is a \*\*Developer Control Plane\*\*—a localized, cognitive operating layer for software creation.



The system was born from the need to manage "cognitive fragmentation". Modern developers juggle multiple projects: some in R\&D, some half-built, and some production-ready. This results in a massive "context-switch tax". Furthermore, current AI coding agents (like Claude Code or Kimi CLI) are amnesic between sessions; they forget the architectural decisions and dependencies from one day to the next.



To solve this, we are building the \*\*Context Fabric\*\*—the persistent memory and nervous system that sits between your local filesystem and your AI agents.



\### The Data Trinity



The architecture is built on a strict Event Sourcing pattern that separates deterministic facts from probabilistic guesses. Everything flows through three immutable layers:



1\. \*\*Raw Signals (Facts):\*\* Deterministic data such as git commits, file modifications, test coverage presence, and open task counts.





2\. \*\*Inferences (Probabilities):\*\* AI or heuristic-driven guesses about the project, such as assigning it a "Development" stage or calculating completion probability. Crucially, all inferences must include a Confidence Score to prevent the "illusion of certainty".





3\. \*\*Decisions (Actions):\*\* System triggers, such as orchestrating an AI agent, suggesting refactors, or marking a project as dormant.







By adhering to this trinity, the system remains a "cognition stabilizer," reducing chaos and allowing for the deliberate allocation of engineering effort.



\---



\## Product Requirements Document (PRD)



\*\*Document Name:\*\* PRD\_Developer\_Control\_Plane

\*\*Status:\*\* V1 Base Specification

\*\*Target Audience:\*\* Engineering, AI Agents, Project Contributors



\### 1. Executive Summary



We are building a local-first, AI-native Developer Control Plane. The system scans a user's local filesystem to discover projects, analyzes raw signals (Git, files, PM tasks) to probabilistically infer project state, and serves as an orchestration hub to launch context-aware AI coding agents natively from the terminal.



\### 2. Core Architectural Principles



\* \*\*Local-First \& Offline-Capable:\*\* The filesystem is the source of truth. The database (SQLite) and background processes run locally.





\* \*\*Event-Driven Modular Monolith:\*\* Internally separated domains (Filesystem, Git, Task Sync, State Engine) communicating via an internal event bus.





\* \*\*AI-Optional:\*\* The system operates purely on fast, deterministic heuristics at Tier 0 (Offline). AI is layered on top for advanced inference but is never a blocking dependency.





\* \*\*Code-Driven Definition of Done (DoD):\*\* Completion percentage is not mystical guesswork; it is derived from explicit, testable assertions defined per project.







\### 3. System Components



The system is divided into three concrete runtime layers:



\#### 3.1 The Sentry (Core Engine)



\* \*\*Function:\*\* A lightweight background daemon.

\* \*\*Responsibilities:\*\*

\* Maintains the "Project Genome" (detected stacks, conventions).





\* Watches the filesystem via OS-level hooks to emit events (e.g., `FileChanged`, `GitStateChanged`) without recursive polling overhead.





\* Manages the local SQLite database as an append-only event log.











\#### 3.2 The Cortex (State \& Inference Engine)



\* \*\*Function:\*\* The analytical brain exposed via a FastAPI REST layer.





\* \*\*Responsibilities:\*\*

\* Consumes raw signals to compute probabilistic project stages (R\&D, Development, Deployed).





\* Acts as the Agent Router, abstracting underlying CLI tools.





\* Context Assembler: Packages recent changes, open tasks, and errors into a payload for AI agents upon invocation.











\#### 3.3 The Interfaces (Thin Clients)



\* \*\*Terminal UI (TUI):\*\* Built first for focus, flow state, and low-latency interaction. Manages embedded terminal multiplexing to launch agents.





\* \*\*Web UI:\*\* Built second for visualization, cross-project analytics, and dashboard clarity.





\* \*Constraint:\* Neither UI contains core logic or talks directly to the filesystem; they strictly consume the Core Engine's API.







\### 4. Feature Specifications



| Feature | Description | Acceptance Criteria |

| --- | --- | --- |

| \*\*Filesystem Intelligence\*\* | Auto-discovers Git and non-Git repos. | Must detect language stacks and infer frameworks locally without cloud API calls.



&#x20;|

| \*\*State Inference\*\* | Automatically tags projects into lifecycle stages. | Must maintain a Bayesian confidence score; confidence must decay if the project is untouched.



&#x20;|

| \*\*Terminal Orchestration\*\* | Launches context-aware AI agents. | Must inject project-specific context (e.g., recent errors, genome) into the agent's prompt upon launch.



&#x20;|

| \*\*Task Synchronization\*\* | Syncs with external tools (Trello). | Must operate primarily offline, queuing sync actions and resolving them upon network connection.



&#x20;|



\### 5. Constraints \& Complexity Budget



\* \*\*No Microservices:\*\* The v1 system must remain a single-process modular monolith to avoid distributed-systems overhead.





\* \*\*Resource Limits:\*\* Must have a near-zero idle CPU footprint; processing is strictly reactive/event-driven.





\* \*\*Hard Limits on Active Work:\*\* The system must enforce constraints (e.g., limiting active projects) to actively reduce cognitive entropy rather than just measuring it.







\### 6. Success Metrics



The system is deemed successful if it achieves the following within 60 days of deployment:



\* Reduces the active project count by surfacing dead or dormant projects.





\* Increases shipped code output by explicitly reducing the context-switching cost.

