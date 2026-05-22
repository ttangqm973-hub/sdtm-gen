import pytest
from lint.sas_lexer import SASLexer
from lint.sas_parser import SASParser


class TestSASParser:
    def test_parse_valid_data_step(self):
        code = "data test; x = 1; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        issues = parser.parse()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_parse_unclosed_data_step(self):
        code = "data test; x = 1;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        issues = parser.parse()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        assert "Unclosed DATA" in errors[0].message

    def test_parse_valid_proc_step(self):
        code = "proc print data=test; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        issues = parser.parse()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_parse_unclosed_proc_step(self):
        code = "proc print data=test;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        issues = parser.parse()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1

    def test_parse_do_block(self):
        code = "data test; do i = 1 to 10; x = i; end; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        issues = parser.parse()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_parse_unclosed_do_block(self):
        code = "data test; do i = 1 to 10; x = i; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        issues = parser.parse()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        assert any("Unclosed DO" in i.message for i in errors)

    def test_parse_select_block(self):
        code = "data test; select(x); when(1) y=1; otherwise y=0; end; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        issues = parser.parse()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_count_data_steps(self):
        code = "data a; run; data b; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        parser.parse()
        assert parser.data_step_count == 2

    def test_count_proc_steps(self):
        code = "proc print; run; proc means; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        parser = SASParser(tokens)
        parser.parse()
        assert parser.proc_step_count == 2
