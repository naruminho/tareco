import sys

import tareco as tc
from tareco import checkup as doctor_module
from tareco.cli import main


def test_doctor_without_spark():
    report = tc.doctor(quick=True)
    assert report.ok, repr(report)
    names = [c.name for c in report]
    assert names[:3] == ["environment", "algorithms", "explain"]
    assert report[-1].name == "spark" and report[-1].status == "skip"
    assert "tareco doctor: all good" in repr(report)
    assert report._repr_markdown_().startswith("**tareco doctor: all good**")


def test_doctor_reports_failures_and_keeps_going(monkeypatch):
    def broken():
        raise RuntimeError("canvas exploded")
    monkeypatch.setattr(doctor_module, "_canvas_page", broken)
    report = tc.doctor(quick=True)
    assert not report.ok and [c.name for c in report.failures] == ["canvas page"]
    assert "RuntimeError: canvas exploded" in report.failures[0].detail
    assert report[-1].name == "spark"  # later checks still ran
    assert "FAIL  canvas page" in repr(report)


def test_doctor_sees_databricks(monkeypatch):
    monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "17.3")
    env = tc.doctor(quick=True)[0]
    assert "Databricks 17.3" in env.detail and "budget 9 MB" in env.detail


def test_cli_doctor(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tareco", "--doctor"])
    monkeypatch.setattr(doctor_module, "_webgl_page", lambda quick: "skipped in this test")
    monkeypatch.setattr(doctor_module, "_notebook_output", lambda quick: "skipped in this test")
    assert main(["--doctor"]) == 0
    assert "tareco doctor: all good" in capsys.readouterr().out
