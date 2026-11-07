import pytest

from patentic.report.bundle import ReportBundle
from tests.report.helpers import demo_bundle


@pytest.fixture(scope="session")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> ReportBundle:
    return demo_bundle(tmp_path_factory.mktemp("bundle"))
