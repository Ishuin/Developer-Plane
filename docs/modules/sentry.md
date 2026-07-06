# sentry

Filesystem intelligence. Three files, three jobs:

- `detectors.py` — declarative stack detection (strategy pattern). Each `Detector` lists marker files and source extensions; `detect()` returns the stack name. Add a language by appending one line to `DETECTORS`.
- `discovery.py` — `ProjectDiscovery.scan(root)`: walks the tree, skips `EXCLUDED_DIRS` (build output, deps, VCS internals), marks roots by strong indicators or ≥3 source files, keeps monorepo children that have their own manifests, then upserts the projection and logs `ProjectDiscovered` signals.
- `watcher.py` — `SentryWatcher`: watchdog-based OS hooks emitting `FileChanged/Created/Deleted/Moved` signals; ignores noise (`.git`, `__pycache__`, `*.db`, …).
- `genome.py` — `build_genome(path)`: cheap one-listing identity: stack, markers, tests/CI/docs/docker presence, git branch + last commit + dirty count.

Related: [[cortex]], [[database]]
