import logging

from server import job_manager


def test_job_manager_defines_module_logger():
    """Creative jobs call log.info before invoking the generation pipeline."""
    assert isinstance(job_manager.log, logging.Logger)
    assert job_manager.log.name == "server.job_manager"
