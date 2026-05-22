import pytest
from lint.sas_lexer import SASLexer, TokenType


class TestSASLexer:
    def test_tokenize_simple_data_step(self):
        code = "data test; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        keywords = [t for t in tokens if t.type == TokenType.KEYWORD]
        assert any(t.value.upper() == "DATA" for t in keywords)
        assert any(t.value.upper() == "RUN" for t in keywords)

    def test_tokenize_string_literal(self):
        code = 'x = "hello";'
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        strings = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strings) == 1
        assert strings[0].value == '"hello"'

    def test_tokenize_number(self):
        code = "x = 42;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        numbers = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(numbers) == 1
        assert numbers[0].value == "42"

    def test_tokenize_comment_block(self):
        code = "/* this is a comment */ data test; run;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        comments = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comments) == 1
        assert "/* this is a comment */" in comments[0].value

    def test_tokenize_macro_call(self):
        code = "%let x = 1;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        macros = [t for t in tokens if t.type == TokenType.MACRO]
        assert any(t.value == "%let" for t in macros)

    def test_tokenize_identifier(self):
        code = "myvar = 1;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert any(t.value == "myvar" for t in identifiers)

    def test_tokenize_operator(self):
        code = "x = y + z;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        operators = [t for t in tokens if t.type == TokenType.OPERATOR]
        assert any(t.value == "=" for t in operators)
        assert any(t.value == "+" for t in operators)

    def test_tokenize_multiline(self):
        code = "data test;\n  x = 1;\nrun;"
        lexer = SASLexer(code)
        tokens = lexer.tokenize()
        newlines = [t for t in tokens if t.type == TokenType.NEWLINE]
        assert len(newlines) == 2
