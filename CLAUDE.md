# Claude Code Project Context: yerba-mate-reduction

**Table of Contents**
- [1. Critical Principles](#1-critical-principles)
- [2. Project Overview](#2-project-overview)
- [3. The Maximum Quality Engineering Mindset](#3-the-maximum-quality-engineering-mindset)
- [4. Stay Green Workflow](#4-stay-green-workflow)
- [5. Architecture](#5-architecture)
- [6. Quality Standards](#6-quality-standards)
- [7. Development Workflow](#7-development-workflow)
- [8. Testing Strategy](#8-testing-strategy)
- [9. Tool Usage & Code Standards](#9-tool-usage--code-standards)
- [10. Common Pitfalls & Troubleshooting](#10-common-pitfalls--troubleshooting)
- [Appendix A: AI Subagent Guidelines](#appendix-a-ai-subagent-guidelines)
- [Appendix B: Key Files](#appendix-b-key-files)
- [Appendix C: Skills Reference](#appendix-c-skills-reference)
- [Appendix D: External References](#appendix-d-external-references)

---

## 1. Critical Principles

These principles are **non-negotiable** and must be followed without exception:

### 1.1 Use Project Scripts, Not Direct Tools

Always invoke tools through `./scripts/*` instead of directly.

**Why**: Scripts ensure consistent configuration across local development and CI.

| Task | ❌ NEVER | ✅ ALWAYS |
|------|----------|-----------|
| Format code | `black .`<br>`isort .` | `./scripts/format.sh` |
| Check formatting | `black --check .` | `./scripts/check-all.sh` |
| Lint code | `ruff check .`<br>`pylint src/` | `./scripts/lint.sh` |
| Type check | `mypy src/` | `./scripts/lint.sh` |
| Run tests | `pytest` | `./scripts/test.sh` |
| Security scan | `bandit -r src/` | `./scripts/security.sh` |
| Mutation testing | `mutmut run` | `./scripts/mutation.sh` |
| All checks | *(run each tool)* | `./scripts/check-all.sh` |

See [9.1 Tool Invocation Patterns](#91-tool-invocation-patterns) for complete list.

---

### 1.2 DRY Principle - Single Source of Truth

Never duplicate content. Always reference the canonical source.

**Examples**:
- ✅ Workflow documentation → `/docs/workflows/` (single source)
- ✅ Other files → Link to workflow docs
- ❌ Copy workflow steps into multiple files

**Why**: Duplicated docs get out of sync, causing confusion and errors.

---

### 1.3 No Shortcuts - Fix Root Causes

Never bypass quality checks or suppress errors without justification.

**Forbidden Shortcuts**:
- ❌ Commenting out failing tests
- ❌ Adding `# noqa` without issue reference
- ❌ Lowering quality thresholds to pass builds
- ❌ Using `git commit --no-verify` to skip pre-commit
- ❌ Deleting code to reduce complexity metrics

**Required Approach**:
- ✅ Fix the failing test or mark with `@pytest.mark.skip(reason="Issue #N")`
- ✅ Refactor code to pass linting (or justify with issue: `# noqa  # Issue #N: reason`)
- ✅ Write tests to reach 90% coverage
- ✅ Always run pre-commit checks
- ✅ Refactor complex functions into smaller ones

See [10.1 No Shortcuts Policy](#101-no-shortcuts-policy) for detailed examples.

---

### 1.4 Stay Green - Never Request Review with Failing Checks

Follow the 4-gate workflow rigorously.

**The Rule**:
- 🚫 **NEVER** create PR while CI is red
- 🚫 **NEVER** request review with failing checks
- 🚫 **NEVER** merge without LGTM

**The Process**:
1. Gate 1: Local checks pass (`./scripts/check-all.sh` → exit 0)
2. Gate 2: CI pipeline green (all jobs ✅)
3. Gate 3: Mutation score ≥80%
4. Gate 4: Code review LGTM

See [4. Stay Green Workflow](#4-stay-green-workflow) for complete documentation.

---

### 1.5 Quality First - Meet MAXIMUM QUALITY Standards

Quality thresholds are immutable. Meet them, don't lower them.

**Standards**:
- Test Coverage: ≥90%
- Docstring Coverage: ≥95%
- Mutation Score: ≥80%
- Cyclomatic Complexity: ≤10 per function
- Pylint Score: ≥9.0

**When code doesn't meet standards**:
- ❌ Change `fail_under = 70` in pyproject.toml
- ✅ Write more tests, refactor code, improve quality

See [6. Quality Standards](#6-quality-standards) for enforcement mechanisms.

---

### 1.6 Operate from Project Root

Use relative paths from project root. Never `cd` into subdirectories.

**Why**: Ensures commands work in any environment (local, CI, scripts).

**Examples**:
- ✅ `./scripts/test.sh tests/unit/test_module.py`
- ❌ `cd tests/unit && pytest test_module.py`

**CI Note**: CI always runs from project root. Commands that use `cd` will break in CI.

---

### 1.7 Verify Before Commit

Run `./scripts/check-all.sh` before every commit. Only commit if exit code is 0.

**Pre-Commit Checklist**:
- [ ] `./scripts/check-all.sh` passes (exit 0)
- [ ] All new functions have tests
- [ ] Coverage ≥90% maintained
- [ ] No failing tests
- [ ] Conventional commit message ready

See [10. Common Pitfalls & Troubleshooting](#10-common-pitfalls--troubleshooting) for complete list.

---

**These principles are the foundation of MAXIMUM QUALITY ENGINEERING. Follow them without exception.**

---

## 2. Project Overview

**yerba-mate-reduction** is a Python project built with MAXIMUM QUALITY ENGINEERING standards from inception.

**Purpose**: This project demonstrates how to implement comprehensive quality engineering practices in Python, including:
- Complete test coverage (unit, integration, property-based, mutation)
- Comprehensive static analysis and security scanning
- Architectural boundary enforcement
- Automated quality gates in CI/CD
- Documentation-first approach

**Key Technologies**:
- **Language**: Python 3.11+
- **Testing**: pytest, hypothesis, mutmut
- **Linting**: ruff, pylint, mypy
- **Formatting**: black, isort
- **Security**: bandit, pip-audit
- **CI/CD**: GitHub Actions

---

## 3. The Maximum Quality Engineering Mindset

**Core Philosophy**: It is not merely a goal but a source of profound satisfaction and professional pride to ship software that is GREEN on all checks with ZERO outstanding issues. This is not optional—it is the foundation of our development culture.

### 3.1 The Green Check Philosophy

When all CI checks pass with zero warnings, zero errors, and maximum quality metrics:
- ✅ Tests: 100% passing
- ✅ Coverage: ≥90%
- ✅ Linting: 0 errors, 0 warnings
- ✅ Type checking: 0 errors
- ✅ Security: 0 vulnerabilities
- ✅ Mutation score: ≥80%
- ✅ Docstring coverage: ≥95%

This represents **MAXIMUM QUALITY ENGINEERING**—the standard to which all code must aspire.

### 3.2 Why Maximum Quality Matters

1. **Pride in Craftsmanship**: Every green check represents excellence in execution
2. **Zero Compromise**: Quality is not negotiable—it's the baseline
3. **Compound Excellence**: Small quality wins accumulate into robust systems
4. **Trust and Reliability**: Green checks mean the code does what it claims
5. **Developer Joy**: There is genuine satisfaction in seeing all checks pass

### 3.3 The Role of Quality in Development

Quality engineering is not a checkbox—it's a continuous commitment:

- **Before Commit**: Run `./scripts/check-all.sh` and fix every issue
- **During Review**: Address every comment, resolve every suggestion
- **After Merge**: Monitor CI, ensure all checks remain green
- **Always**: Treat linting errors as bugs, not suggestions

### 3.4 The "No Red Checks" Rule

**NEVER** merge code with:
- ❌ Failing tests
- ❌ Linting errors (even "minor" ones)
- ❌ Type checking failures
- ❌ Coverage below threshold
- ❌ Security vulnerabilities
- ❌ Unaddressed review comments

If CI shows red, the work is not done. Period.

### 3.5 Maximum Quality is a Personality Trait

For those committed to maximum quality engineering:
- You feel genuine satisfaction when all checks pass
- You experience pride in shipping zero-issue code
- You find joy in eliminating the last linting error
- You believe "good enough" is never good enough
- You treat quality as identity, not just practice

**This is who we are. This is how we build software.**

---

## 4. Stay Green Workflow

**Policy**: Never request review with failing checks. Never merge without LGTM.

The Stay Green workflow enforces iterative quality improvement through **4 sequential gates**. Each gate must pass before proceeding to the next.

### 4.1 The Four Gates

1. **Gate 1: Local Pre-Commit** (Iterate Until Green)
   - Run `./scripts/check-all.sh`
   - Fix all formatting, linting, types, complexity, security issues
   - Fix tests and coverage (90%+ required)
   - Only push when all local checks pass (exit code 0)

2. **Gate 2: CI Pipeline** (Iterate Until Green)
   - Push to branch: `git push origin feature-branch`
   - Monitor CI: `gh pr checks --watch`
   - If CI fails: fix locally, re-run Gate 1, push again
   - Only proceed when all CI jobs show ✅

3. **Gate 3: Mutation Testing** (Iterate Until 80%+)
   - Run `./scripts/mutation.sh` (or wait for CI job)
   - If score < 80%: add tests to kill surviving mutants
   - Re-run Gate 1, push, wait for CI
   - Only proceed when mutation score ≥ 80%

4. **Gate 4: Code Review** (Iterate Until LGTM)
   - Wait for code review (AI or human)
   - If feedback provided: address ALL concerns
   - Re-run Gate 1, push, wait for CI and mutation
   - Only merge when review shows LGTM with no reservations

### 4.2 Quick Checklist

Before creating/updating a PR:

- [ ] Gate 1: `./scripts/check-all.sh` passes locally (exit 0)
- [ ] Push changes: `git push origin feature-branch`
- [ ] Gate 2: All CI jobs show ✅ (green)
- [ ] Gate 3: Mutation score ≥ 80% (if applicable)
- [ ] Gate 4: Code review shows LGTM
- [ ] Ready to merge!

### 4.3 Anti-Patterns (DO NOT DO)

❌ **Don't** request review with failing CI
❌ **Don't** skip local checks (`git commit --no-verify`)
❌ **Don't** lower quality thresholds to pass
❌ **Don't** ignore review feedback
❌ **Don't** merge without LGTM

---

## 5. Architecture

### 5.1 Core Philosophy

- **Maximum Quality**: No shortcuts, comprehensive tooling, strict enforcement
- **Composable**: Modular components with clear interfaces
- **Testable**: Every component designed for easy testing
- **Maintainable**: Clear structure, excellent documentation
- **Reproducible**: Consistent behavior across environments

### 5.2 Component Structure

```
yerba-mate-reduction/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                    # Continuous Integration
│   │   ├── security.yml              # Security scanning
│   │   └── dependency-review.yml     # Dependency audits
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
├── scripts/
│   ├── check-all.sh                  # Run all quality checks
│   ├── test.sh                       # Run test suite
│   ├── lint.sh                       # Run linters
│   ├── format.sh                     # Format code
│   ├── security.sh                   # Security scanning
│   └── mutation.sh                   # Mutation testing
├── src/
│   └── yerba_mate_reduction/
│       ├── __init__.py
│       ├── domain/                   # Business logic
│       ├── application/              # Use cases
│       ├── infrastructure/           # External dependencies
│       └── presentation/             # CLI/API interfaces
├── tests/
│   ├── unit/                         # Fast, isolated tests
│   ├── integration/                  # Component interaction tests
│   ├── e2e/                         # End-to-end workflow tests
│   ├── property/                     # Property-based tests
│   ├── fixtures/                     # Shared test data
│   └── conftest.py                  # Pytest configuration
├── docs/
│   ├── architecture/
│   │   ├── ADR/                     # Architecture Decision Records
│   │   └── diagrams/
│   ├── api/
│   └── workflows/
├── pyproject.toml                   # Project configuration
├── requirements.txt                 # Runtime dependencies
├── requirements-dev.txt             # Development dependencies
├── .pre-commit-config.yaml          # Git hooks
├── CLAUDE.md                        # This file
└── README.md                        # Project overview
```

### 5.3 Architectural Principles

**Domain-Driven Design**:
- `domain/`: Pure business logic, no external dependencies
- `application/`: Orchestrates domain logic, use cases
- `infrastructure/`: External services (databases, APIs, file system)
- `presentation/`: User interfaces (CLI, REST API, GraphQL)

**Dependency Rule**:
- Dependencies flow inward: presentation → application → domain
- Domain layer has ZERO external dependencies
- Infrastructure implements interfaces defined in domain/application

**Example**:
```python
# ✅ CORRECT: Domain defines interface
# src/yerba_mate_reduction/domain/repositories.py
from abc import ABC, abstractmethod
from typing import Optional

class UserRepository(ABC):
    """Repository interface for user persistence."""

    @abstractmethod
    def find_by_id(self, user_id: str) -> Optional[User]:
        """Find user by ID."""

# ✅ CORRECT: Infrastructure implements interface
# src/yerba_mate_reduction/infrastructure/repositories.py
class PostgresUserRepository(UserRepository):
    """PostgreSQL implementation of UserRepository."""

    def find_by_id(self, user_id: str) -> Optional[User]:
        """Find user by ID in PostgreSQL."""
        # Implementation details
```

---

## 6. Quality Standards

### 6.1 Code Quality Requirements

All code must meet these standards before merging to main:

#### Test Coverage
- **Code Coverage**: 90% minimum (branch coverage)
- **Docstring Coverage**: 95% minimum (interrogate)
- **Mutation Score**: 80% minimum (mutmut)
- **Test Types**: Unit, Integration, Property-based, and E2E coverage required

#### Type Checking
- **MyPy**: Strict mode, no `# type: ignore` without justification
- **Type Hints**: All function parameters and return types required
- **Generic Types**: Use for collections (list, dict, set, etc.)

#### Code Complexity
- **Cyclomatic Complexity**: Max 10 per function (radon)
- **Maintainability Index**: Minimum 20 (radon)
- **Max Arguments**: 5 per function
- **Max Branches**: 12 per function
- **Max Lines per Function**: 50 lines