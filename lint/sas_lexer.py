import re
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class TokenType(Enum):
    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    STRING = "STRING"
    NUMBER = "NUMBER"
    OPERATOR = "OPERATOR"
    PUNCTUATION = "PUNCTUATION"
    COMMENT = "COMMENT"
    MACRO = "MACRO"
    WHITESPACE = "WHITESPACE"
    NEWLINE = "NEWLINE"
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int


class SASLexer:
    KEYWORDS = {
        "DATA", "RUN", "PROC", "QUIT", "SET", "MERGE", "UPDATE", "MODIFY",
        "BY", "WHERE", "IF", "THEN", "ELSE", "DO", "END", "SELECT", "WHEN",
        "OTHERWISE", "OUTPUT", "RETURN", "GOTO", "LABEL", "FORMAT", "INFORMAT",
        "INPUT", "PUT", "CARDS", "DATALINES", "INFILE", "FILE", "KEEP", "DROP",
        "RENAME", "RETAIN", "SUM", "MEAN", "MIN", "MAX", "LENGTH", "ATTRIB",
        "ARRAY", "CALL", "STOP", "ABORT", "DELETE", "REMOVE",
        "LIBNAME", "FILENAME", "OPTIONS", "TITLE", "FOOTNOTE",
        "GLOBAL", "LOCAL", "NULL", "IN", "NOT", "AND", "OR",
        "EQ", "NE", "GT", "LT", "GE", "LE", "CONTAINS", "BETWEEN", "LIKE",
    }

    MACRO_KEYWORDS = {
        "%macro", "%mend", "%let", "%if", "%then", "%else", "%do", "%end",
        "%include", "%put", "%eval", "%sysfunc", "%str", "%nrstr",
        "%bquote", "%nrbquote", "%superq", "%goto", "%return",
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break

            char = self.source[self.pos]

            if char == "\n":
                self.tokens.append(Token(TokenType.NEWLINE, "\n", self.line, self.column))
                self._advance()
                self.line += 1
                self.column = 1
            elif char == "/" and self._peek(1) == "*":
                self._read_comment()
            elif char == "*" and self._is_at_line_start():
                self._read_comment_star()
            elif char in ('"', "'"):
                self._read_string(char)
            elif char.isdigit() or (char == "." and self._peek(1) and self._peek(1).isdigit()):
                self._read_number()
            elif char.isalpha() or char == "_":
                self._read_identifier()
            elif char == "%":
                self._read_macro()
            elif char in "=<>!&|+-*/^;:,.()[]{}":
                self._read_operator_or_punctuation()
            else:
                self._advance()

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens

    def _advance(self):
        self.pos += 1
        self.column += 1

    def _peek(self, offset: int = 0) -> Optional[str]:
        pos = self.pos + offset
        if pos < len(self.source):
            return self.source[pos]
        return None

    def _is_at_line_start(self) -> bool:
        pos = self.pos - 1
        while pos >= 0 and self.source[pos] in " \t":
            pos -= 1
        return pos < 0 or self.source[pos] == "\n"

    def _skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos] in " \t\r":
            self._advance()

    def _read_comment(self):
        start_col = self.column
        start_line = self.line
        self._advance()
        self._advance()
        value = "/*"
        while self.pos < len(self.source):
            if self.source[self.pos] == "*" and self._peek(1) == "/":
                value += "*/"
                self._advance()
                self._advance()
                break
            if self.source[self.pos] == "\n":
                self.line += 1
                self.column = 0
            value += self.source[self.pos]
            self._advance()
        self.tokens.append(Token(TokenType.COMMENT, value, start_line, start_col))

    def _read_comment_star(self):
        start_col = self.column
        start_line = self.line
        value = "*"
        self._advance()
        while self.pos < len(self.source):
            if self.source[self.pos] == ";":
                value += ";"
                self._advance()
                break
            if self.source[self.pos] == "\n":
                self.line += 1
                self.column = 0
            value += self.source[self.pos]
            self._advance()
        self.tokens.append(Token(TokenType.COMMENT, value, start_line, start_col))

    def _read_string(self, quote: str):
        start_col = self.column
        start_line = self.line
        value = quote
        self._advance()
        while self.pos < len(self.source):
            char = self.source[self.pos]
            value += char
            if char == quote:
                self._advance()
                if self.pos < len(self.source) and self.source[self.pos] == quote:
                    value += quote
                    self._advance()
                    continue
                break
            if char == "\n":
                self.line += 1
                self.column = 0
            self._advance()
        self.tokens.append(Token(TokenType.STRING, value, start_line, start_col))

    def _read_number(self):
        start_col = self.column
        value = ""
        has_dot = False
        has_exp = False
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char.isdigit():
                value += char
                self._advance()
            elif char == "." and not has_dot:
                value += char
                has_dot = True
                self._advance()
            elif char in "eE" and not has_exp:
                value += char
                has_exp = True
                self._advance()
                if self.pos < len(self.source) and self.source[self.pos] in "+-":
                    value += self.source[self.pos]
                    self._advance()
            else:
                break
        self.tokens.append(Token(TokenType.NUMBER, value, self.line, start_col))

    def _read_identifier(self):
        start_col = self.column
        start_line = self.line
        value = ""
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char.isalnum() or char == "_":
                value += char
                self._advance()
            else:
                break
        upper_value = value.upper()
        if upper_value in self.KEYWORDS:
            self.tokens.append(Token(TokenType.KEYWORD, value, start_line, start_col))
        else:
            self.tokens.append(Token(TokenType.IDENTIFIER, value, start_line, start_col))

    def _read_macro(self):
        start_col = self.column
        start_line = self.line
        value = "%"
        self._advance()
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char.isalnum() or char == "_":
                value += char
                self._advance()
            else:
                break
        self.tokens.append(Token(TokenType.MACRO, value, start_line, start_col))

    def _read_operator_or_punctuation(self):
        start_col = self.column
        char = self.source[self.pos]
        two_char_ops = ["<=", ">=", "<>", "!!", "||", "&&", "||", "**"]
        if self.pos + 1 < len(self.source):
            two_char = char + self.source[self.pos + 1]
            if two_char in two_char_ops:
                self._advance()
                self._advance()
                self.tokens.append(Token(TokenType.OPERATOR, two_char, self.line, start_col))
                return
        if char in "=<>!&|+-*/^":
            self._advance()
            self.tokens.append(Token(TokenType.OPERATOR, char, self.line, start_col))
        else:
            self._advance()
            self.tokens.append(Token(TokenType.PUNCTUATION, char, self.line, start_col))
