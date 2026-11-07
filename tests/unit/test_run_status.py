from patentic.runner import run_status


def test_run_status_reflects_final_stage() -> None:
    assert run_status("validated") == "completed"
    assert run_status("aborted") == "aborted"
    assert run_status("validation_failed") == "validation_failed"
