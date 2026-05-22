from dataclasses import dataclass, field
from typing import List, Optional
from lint.sas_lexer import Token, TokenType


@dataclass
class LintIssue:
    line: int
    column: int
    message: str
    severity: str = "error"


@dataclass
class BlockInfo:
    block_type: str
    start_line: int
    end_line: Optional[int] = None
    is_closed: bool = False


class SASParser:
    def __init__(self, tokens: List[Token]):
        self.tokens = [t for t in tokens if t.type not in (TokenType.WHITESPACE,)]
        self.pos = 0
        self.issues: List[LintIssue] = []
        self.blocks: List[BlockInfo] = []
        self.data_step_count = 0
        self.proc_step_count = 0

    def parse(self) -> List[LintIssue]:
        self._parse_program()
        self._check_unclosed_blocks()
        return self.issues

    def _current(self) -> Optional[Token]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _peek(self, offset: int = 1) -> Optional[Token]:
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return None

    def _advance(self):
        self.pos += 1

    def _match(self, *types: TokenType) -> bool:
        token = self._current()
        return token is not None and token.type in types

    def _match_value(self, value: str, case_insensitive: bool = True) -> bool:
        token = self._current()
        if token is None:
            return False
        if case_insensitive:
            return token.value.upper() == value.upper()
        return token.value == value

    def _parse_program(self):
        while self._current() is not None:
            self._parse_statement()

    def _is_dataset_option(self):
        """Check if current 'data' keyword is actually a dataset option (data=)"""
        next_token = self._peek(1)
        return next_token is not None and next_token.value == "="

    def _parse_statement(self):
        token = self._current()
        if token is None:
            return

        if token.type == TokenType.KEYWORD:
            upper_val = token.value.upper()
            if upper_val == "DATA" and not self._is_dataset_option():
                self._parse_data_step()
            elif upper_val == "PROC":
                self._parse_proc_step()
            elif upper_val == "RUN":
                self._handle_run_statement()
                self._advance()
            elif upper_val == "QUIT":
                self._handle_quit_statement()
                self._advance()
            elif upper_val == "DO":
                self._parse_do_block()
            elif upper_val == "SELECT":
                self._parse_select_block()
            elif upper_val in ("IF", "ELSE", "WHERE", "BY", "SET", "MERGE",
                               "UPDATE", "MODIFY", "OUTPUT", "RETURN", "KEEP",
                               "DROP", "RENAME", "RETAIN", "LENGTH", "ATTRIB",
                               "ARRAY", "FORMAT", "INFORMAT", "LABEL"):
                self._parse_simple_statement()
            else:
                self._advance()
        elif token.type == TokenType.MACRO:
            self._parse_macro_statement()
        else:
            self._advance()

    def _parse_data_step(self):
        token = self._current()
        if token:
            self.blocks.append(BlockInfo("DATA", token.line))
            self.data_step_count += 1
        self._advance()
        while self._current() is not None:
            if self._match(TokenType.KEYWORD) and self._current().value.upper() == "RUN":
                block = self._find_unclosed_data_or_proc_block()
                if block and block.block_type == "DATA":
                    block.is_closed = True
                    block.end_line = self._current().line
                self._advance()
                break
            self._parse_statement()

    def _parse_proc_step(self):
        token = self._current()
        if token:
            self.blocks.append(BlockInfo("PROC", token.line))
            self.proc_step_count += 1
        self._advance()
        while self._current() is not None:
            if self._match(TokenType.KEYWORD) and self._current().value.upper() in ("RUN", "QUIT"):
                block = self._find_unclosed_data_or_proc_block()
                if block and block.block_type == "PROC":
                    block.is_closed = True
                    block.end_line = self._current().line
                self._advance()
                break
            self._parse_statement()

    def _find_unclosed_data_or_proc_block(self):
        for block in reversed(self.blocks):
            if block.block_type in ("DATA", "PROC") and not block.is_closed:
                return block
        return None

    def _handle_run_statement(self):
        block = self._find_unclosed_data_or_proc_block()
        if block:
            block.is_closed = True
            block.end_line = self._current().line if self._current() else None

    def _handle_quit_statement(self):
        for block in reversed(self.blocks):
            if block.block_type == "PROC" and not block.is_closed:
                block.is_closed = True
                block.end_line = self._current().line if self._current() else None
                break

    def _parse_do_block(self):
        token = self._current()
        if token:
            self.blocks.append(BlockInfo("DO", token.line))
        self._advance()
        depth = 1
        while self._current() is not None and depth > 0:
            if self._match(TokenType.KEYWORD):
                upper_val = self._current().value.upper()
                if upper_val == "DO":
                    depth += 1
                    self.blocks.append(BlockInfo("DO", self._current().line))
                elif upper_val == "END":
                    depth -= 1
                    if self.blocks and self.blocks[-1].block_type == "DO":
                        self.blocks[-1].is_closed = True
                        self.blocks[-1].end_line = self._current().line
            self._advance()

    def _parse_select_block(self):
        token = self._current()
        if token:
            self.blocks.append(BlockInfo("SELECT", token.line))
        self._advance()
        while self._current() is not None:
            if self._match(TokenType.KEYWORD):
                upper_val = self._current().value.upper()
                if upper_val == "END":
                    if self.blocks and self.blocks[-1].block_type == "SELECT":
                        self.blocks[-1].is_closed = True
                        self.blocks[-1].end_line = self._current().line
                    self._advance()
                    break
            self._advance()

    def _parse_simple_statement(self):
        while self._current() is not None:
            if self._match(TokenType.PUNCTUATION) and self._current().value == ";":
                self._advance()
                break
            self._advance()

    def _parse_macro_statement(self):
        token = self._current()
        if token:
            upper_val = token.value.upper()
            if upper_val == "%MACRO":
                self.blocks.append(BlockInfo("MACRO", token.line))
            elif upper_val == "%MEND":
                for block in reversed(self.blocks):
                    if block.block_type == "MACRO" and not block.is_closed:
                        block.is_closed = True
                        block.end_line = token.line
                        break
        self._advance()

    def _check_unclosed_blocks(self):
        for block in self.blocks:
            if not block.is_closed:
                self.issues.append(LintIssue(
                    line=block.start_line,
                    column=1,
                    message=f"Unclosed {block.block_type} block started at line {block.start_line}",
                    severity="error"
                ))
