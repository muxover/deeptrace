import importlib.util
import os

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills", "deeptrace", "scripts")


def load(name, filename):
    path = os.path.join(SCRIPTS, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def scripts_dir():
    return SCRIPTS


@pytest.fixture(scope="session")
def recon():
    return load("recon", "recon.py")


@pytest.fixture(scope="session")
def runner():
    return load("run", "run.py")


@pytest.fixture(scope="session")
def tracer():
    return load("trace", "trace.py")


@pytest.fixture(scope="session")
def trace_go():
    return load("trace_go", "trace-go.py")


@pytest.fixture(scope="session")
def trace_rust():
    return load("trace_rust", "trace-rust.py")
