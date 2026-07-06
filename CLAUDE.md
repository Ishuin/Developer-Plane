# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project is a Developer Control Plane - a localized, cognitive operating layer for software creation. It's designed as a "Context Fabric" that serves as persistent memory and nervous system between your local filesystem and AI agents.

## Core Architecture

The system is built on a strict Event Sourcing pattern with three immutable layers:

1. **Raw Signals (Facts)**: Deterministic data such as git commits, file modifications, test coverage presence
2. **Inferences (Probabilities)**: AI or heuristic-driven guesses about the project with confidence scores
3. **Decisions (Actions)**: System triggers such as orchestrating AI agents or suggesting refactors

## System Components

### The Sentry (Core Engine)
- Lightweight background daemon that maintains the "Project Genome"
- Watches filesystem via OS-level hooks to emit events without polling overhead
- Manages local SQLite database as append-only event log

### The Cortex (State & Inference Engine)
- Analytical brain exposed via FastAPI REST layer
- Computes probabilistic project stages (R&D, Development, Deployed)
- Acts as Agent Router and Context Assembler

### The Interfaces (Thin Clients)
- Terminal UI (TUI) for focus and flow state interaction
- Web UI for visualization and dashboard clarity
- Both consume the Core Engine's API only

## Development Guidelines

The system follows these core architectural principles:
- Local-First & Offline-Capable: Filesystem is the source of truth
- Event-Driven Modular Monolith: Separated domains communicating via internal event bus
- AI-Optional: Operates on deterministic heuristics at Tier 0 (Offline)
- Code-Driven Definition of Done: Completion percentage derived from explicit, testable assertions

## Common Development Tasks

When working on this codebase, keep in mind:
- The system should maintain a near-zero idle CPU footprint
- Processing is strictly reactive/event-driven
- No microservices - the system remains a single-process modular monolith
- All core logic resides in the Core Engine, not in UI components