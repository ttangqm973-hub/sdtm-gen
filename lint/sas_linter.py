import re
from dataclasses import dataclass, field
from typing import List, Dict, Any
from lint.sas_lexer import SASLexer, Token, TokenType
from lint.sas_parser import SASParser, LintIssue
from lint.sas_keywords import SAS_KEYWORDS, SAS_PROCEDURES


@dataclass
class LintReport:
    file_path: str
    issues: List[LintIssue]
    stats: Dict[str, Any] = field(default_factory=dict)

    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def has_warnings(self) -> bool:
        return any(issue.severity == "warning" for issue in self.issues)

    def __str__(self) -> str:
        lines = [f"Lint Report: {self.file_path}", "=" * 50]
        if not self.issues:
            lines.append("No issues found.")
        else:
            for issue in self.issues:
                lines.append(f"  Line {issue.line}, Col {issue.column}: [{issue.severity.upper()}] {issue.message}")
        if self.stats:
            lines.append("\nStatistics:")
            for key, value in self.stats.items():
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)


class SASLinter:
    def __init__(self):
        self.keywords = SAS_KEYWORDS
        self.procedures = SAS_PROCEDURES

    def lint(self, source: str, file_path: str = "unnamed.sas") -> LintReport:
        issues = []
        stats = {
            "lines": source.count("\n") + 1,
            "data_steps": 0,
            "proc_steps": 0,
            "macro_calls": 0,
        }

        lexer = SASLexer(source)
        tokens = lexer.tokenize()

        parser = SASParser(tokens)
        parse_issues = parser.parse()
        issues.extend(parse_issues)

        stats["data_steps"] = parser.data_step_count
        stats["proc_steps"] = parser.proc_step_count

        keyword_issues = self._check_reserved_keywords(tokens)
        issues.extend(keyword_issues)

        macro_issues = self._check_macro_calls(tokens, stats)
        issues.extend(macro_issues)

        style_issues = self._check_style_issues(source)
        issues.extend(style_issues)

        return LintReport(file_path=file_path, issues=issues, stats=stats)

    def _check_reserved_keywords(self, tokens: List[Token]) -> List[LintIssue]:
        issues = []
        for i, token in enumerate(tokens):
            if token.type == TokenType.IDENTIFIER:
                upper_val = token.value.upper()
                if upper_val in self.keywords:
                    issues.append(LintIssue(
                        line=token.line,
                        column=token.column,
                        message=f"Variable '{token.value}' conflicts with SAS keyword",
                        severity="warning"
                    ))
            elif token.type == TokenType.KEYWORD:
                next_token = tokens[i + 1] if i + 1 < len(tokens) else None
                if next_token and next_token.type == TokenType.OPERATOR and next_token.value == "=":
                    prev_token = tokens[i - 1] if i > 0 else None
                    if prev_token and prev_token.type == TokenType.PUNCTUATION and prev_token.value == ";":
                        issues.append(LintIssue(
                            line=token.line,
                            column=token.column,
                            message=f"Variable '{token.value}' conflicts with SAS keyword",
                            severity="warning"
                        ))
        return issues

    def _check_macro_calls(self, tokens: List[Token], stats: Dict) -> List[LintIssue]:
        issues = []
        macro_pattern = re.compile(r'%\w+')
        for token in tokens:
            if token.type == TokenType.MACRO:
                stats["macro_calls"] += 1
        return issues

    def _check_style_issues(self, source: str) -> List[LintIssue]:
        issues = []
        lines = source.split("\n")
        for i, line in enumerate(lines, start=1):
            if len(line) > 200:
                issues.append(LintIssue(
                    line=i,
                    column=len(line),
                    message=f"Line exceeds 200 characters ({len(line)} chars)",
                    severity="warning"
                ))
            stripped = line.rstrip()
            if stripped and stripped != line:
                issues.append(LintIssue(
                    line=i,
                    column=len(stripped) + 1,
                    message="Trailing whitespace",
                    severity="info"
                ))
        return issues

    def lint_file(self, file_path: str) -> LintReport:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        return self.lint(source, file_path)
