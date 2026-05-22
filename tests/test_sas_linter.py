import pytest
import tempfile
import os
from lint.sas_linter import SASLinter, LintReport


class TestSASLinter:
    def test_lint_valid_code(self):
        code = """
data test;
    x = 1;
run;
"""
        linter = SASLinter()
        report = linter.lint(code)
        assert not report.has_errors()

    def test_lint_unclosed_data_step(self):
        code = "data test; x = 1;"
        linter = SASLinter()
        report = linter.lint(code)
        assert report.has_errors()

    def test_lint_keyword_conflict(self):
        code = "data test; data = 1; run;"
        linter = SASLinter()
        report = linter.lint(code)
        warnings = [i for i in report.issues if i.severity == "warning"]
        assert any("keyword" in i.message.lower() for i in warnings)

    def test_lint_long_line(self):
        code = "data test; x = '" + "a" * 250 + "'; run;"
        linter = SASLinter()
        report = linter.lint(code)
        warnings = [i for i in report.issues if i.severity == "warning"]
        assert any("200 characters" in i.message for i in warnings)

    def test_lint_stats(self):
        code = """
data test;
    x = 1;
run;

proc print data=test;
run;
"""
        linter = SASLinter()
        report = linter.lint(code)
        assert report.stats["data_steps"] == 1
        assert report.stats["proc_steps"] == 1

    def test_lint_file(self):
        code = "data test; run;"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sas", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name
        try:
            linter = SASLinter()
            report = linter.lint_file(temp_path)
            assert not report.has_errors()
        finally:
            os.unlink(temp_path)

    def test_report_str(self):
        code = "data test; x = 1; run;"
        linter = SASLinter()
        report = linter.lint(code, "test.sas")
        report_str = str(report)
        assert "Lint Report" in report_str
        assert "test.sas" in report_str

    def test_lint_with_macros(self):
        code = """
%let x = 1;
data test;
    y = &x;
run;
"""
        linter = SASLinter()
        report = linter.lint(code)
        assert report.stats["macro_calls"] >= 1
