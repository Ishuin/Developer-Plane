"""Language/stack detection (strategy pattern).

Each detector is declarative data; `detect` scores a directory's file list
against every strategy and returns the best match.
"""

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class Detector:
    name: str
    marker_files: Tuple[str, ...] = ()
    extensions: Tuple[str, ...] = ()
    # Number of matching source files required when no marker file exists.
    min_sources: int = 3


DETECTORS: List[Detector] = [
    Detector("Python", ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"), (".py",)),
    Detector("JavaScript/TypeScript", ("package.json", "tsconfig.json"), (".js", ".jsx", ".ts", ".tsx")),
    Detector("Rust", ("Cargo.toml",), (".rs",)),
    Detector("Go", ("go.mod",), (".go",)),
    Detector("Java/Maven", ("pom.xml",), ()),
    Detector("Java/Gradle", ("build.gradle", "build.gradle.kts"), ()),
    Detector("Java", (), (".java",)),
    Detector("PHP", ("composer.json",), (".php",)),
    Detector("Ruby", ("Gemfile",), (".rb",)),
    Detector("C#", ("packages.config",), (".cs",)),
    Detector("C/C++", ("CMakeLists.txt",), (".c", ".cc", ".cpp", ".cxx", ".h", ".hpp")),
    Detector("Dart/Flutter", ("pubspec.yaml",), (".dart",)),
    Detector("Elixir", ("mix.exs",), (".ex", ".exs")),
]

# Files that definitively mark a directory as a project root.
STRONG_INDICATORS = frozenset(
    marker for d in DETECTORS for marker in d.marker_files
) | {".git"}


def detect(files: Sequence[str]) -> str:
    """Return the stack name for a directory's file list, or "Unknown"."""
    file_set = set(files)

    for detector in DETECTORS:
        if file_set.intersection(detector.marker_files):
            return detector.name

    for detector in DETECTORS:
        if not detector.extensions:
            continue
        sources = [f for f in files if f.endswith(detector.extensions)]
        if len(sources) >= detector.min_sources:
            return detector.name

    return "Unknown"
