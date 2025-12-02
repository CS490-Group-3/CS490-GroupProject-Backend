# Backend Test Suite

## Overview
Comprehensive test suite for the backend API with 70% code coverage target.

## Test Structure
- `unit/` - Unit tests for services and utilities
- `integration/` - Integration tests for API endpoints and flows

## Running Tests

### Install Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=. --cov-report=html
```

### Run Specific Test File
```bash
pytest tests/unit/test_payment_service.py
```

### Run by Marker
```bash
pytest -m unit
pytest -m integration
```

## Coverage Reports
- Terminal: `pytest --cov=. --cov-report=term`
- HTML: `pytest --cov=. --cov-report=html` (opens `htmlcov/index.html`)
- XML: `pytest --cov=. --cov-report=xml` (for CI/CD)

## CI/CD
Tests run automatically on push/PR via GitHub Actions (`.github/workflows/tests.yml`)

