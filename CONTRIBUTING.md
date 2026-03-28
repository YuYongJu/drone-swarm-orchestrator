# Contributing to Drone Swarm Orchestrator

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yuyongju/drone-swarm-orchestrator.git
   cd drone-swarm-orchestrator
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\Scripts\activate      # Windows
   ```

3. **Install in editable mode with dev dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

## Running Tests

```bash
pytest tests/
```

To run a specific test file:
```bash
pytest tests/test_drone.py
```

To run with verbose output:
```bash
pytest tests/ -v
```

## Running the Linter

```bash
ruff check .
```

To auto-fix issues where possible:
```bash
ruff check . --fix
```

## Code Style

- We use **Ruff** for linting and formatting with the config in `ruff.toml`.
- Line length limit is **100 characters**.
- **Type hints are encouraged** on all public functions and methods.
- Follow PEP 8 naming conventions.
- Use `async`/`await` for all I/O-bound operations (MAVLink communication, networking).

## Pull Request Process

1. **Fork** the repository and create a feature branch from `main`:
   ```bash
   git checkout -b my-feature
   ```

2. **Make your changes** with clear, focused commits.

3. **Add or update tests** for any new functionality.

4. **Run the linter and tests** before submitting:
   ```bash
   ruff check .
   pytest tests/
   ```

5. **Push your branch** and open a Pull Request against `main`.

6. **CI must pass** before your PR can be merged. The CI pipeline runs linting and tests across Python 3.11, 3.12, and 3.13.

7. A maintainer will review your PR. Please respond to feedback in a timely manner.

## Good First Issues

Issues labeled **`good first issue`** are specifically chosen for new contributors. They are typically:

- Well-scoped with clear acceptance criteria
- Limited to a single file or module
- Accompanied by pointers on where to start

Browse them at: [Good First Issues](https://github.com/yuyongju/drone-swarm-orchestrator/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

## Questions?

Open a [Discussion](https://github.com/yuyongju/drone-swarm-orchestrator/discussions) or reach out in an issue. We're happy to help!
