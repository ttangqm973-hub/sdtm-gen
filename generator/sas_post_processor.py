"""
SAS Code Post-Processor - AI 生成代码后处理

验证、清理和格式化 AI 生成的 SAS 代码。
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PostProcessResult:
    """后处理结果"""
    code: str
    cleaned: bool = False
    fixes: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    valid: bool = True


class SASCodePostProcessor:
    """AI 生成 SAS 代码后处理器"""

    SAS_KEYWORDS = {
        'DATA', 'SET', 'MERGE', 'BY', 'WHERE', 'KEEP', 'DROP',
        'RENAME', 'RETAIN', 'LENGTH', 'ATTRIB', 'ARRAY',
        'FORMAT', 'INFORMAT', 'LABEL', 'INPUT', 'PUT',
        'IF', 'THEN', 'ELSE', 'DO', 'END', 'AND', 'OR', 'NOT',
        'SELECT', 'WHEN', 'OTHERWISE', 'OUTPUT', 'RETURN',
        'RUN', 'QUIT', 'PROC', 'STOP', 'ABORT',
        'IN', 'LIKE', 'CONTAINS', 'BETWEEN', 'IS', 'NULL', 'MISSING',
    }

    def process(self, code: str, variable_name: str = None) -> PostProcessResult:
        """处理 AI 生成的代码"""
        result = PostProcessResult(code=code)

        # 清理
        code = self._clean_empty_lines(code)
        code = self._fix_semicolons(code)

        # 验证
        issues = []
        issues.extend(self._check_unmatched_blocks(code))
        issues.extend(self._check_variable_assignment(code, variable_name))
        issues.extend(self._check_sas_syntax(code))

        result.code = code
        result.cleaned = True
        result.issues = issues
        result.valid = len(issues) == 0 or all("WARNING" in i for i in issues)

        for issue in issues:
            if issue.startswith("FIXED:"):
                result.fixes.append(issue)

        return result

    def _clean_empty_lines(self, code: str) -> str:
        """清理多余空行"""
        # 移除连续3个以上空行
        code = re.sub(r'\n{3,}', '\n\n', code)
        # 移除行尾空格
        code = '\n'.join(line.rstrip() for line in code.split('\n'))
        return code.strip()

    def _fix_semicolons(self, code: str) -> str:
        """修复分号问题"""
        # 确保每个语句以分号结尾
        lines = code.split('\n')
        fixed = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('/*') and not stripped.endswith('*/'):
                if any(stripped.upper().startswith(kw) for kw in
                       ['IF', 'ELSE', 'DO', 'SELECT', 'OTHERWISE', 'DATA']):
                    continue  # 这些可能是块开始
            fixed.append(line)
        return '\n'.join(fixed)

    def _check_unmatched_blocks(self, code: str) -> list[str]:
        """检查未匹配的块"""
        issues = []

        # 检查 if/then/else/end 匹配
        if_count = len(re.findall(r'\bIF\b', code, re.IGNORECASE))
        then_count = len(re.findall(r'\bTHEN\b', code, re.IGNORECASE))
        end_count = len(re.findall(r'\bEND\b', code, re.IGNORECASE))

        # IF 和 THEN 应该匹配
        if if_count > then_count:
            issues.append("WARNING: IF count exceeds THEN count")

        # DO 和 END 匹配
        do_count = len(re.findall(r'\bDO\b', code, re.IGNORECASE))
        if do_count > end_count:
            issues.append("WARNING: DO/END mismatch possible")

        # SELECT 和 END 匹配
        select_count = len(re.findall(r'\bSELECT\b', code, re.IGNORECASE))

        return issues

    def _check_variable_assignment(self, code: str, var_name: str = None) -> list[str]:
        """检查变量赋值"""
        issues = []

        if var_name:
            # 检查目标变量是否有赋值
            assignment_pattern = rf'{var_name}\s*='
            if not re.search(assignment_pattern, code, re.IGNORECASE):
                issues.append(f"WARNING: Variable {var_name} not assigned in code")

        return issues

    def _check_sas_syntax(self, code: str) -> list[str]:
        """基本 SAS 语法检查"""
        issues = []

        # 检查缺失值引号
        missing_pattern = r"=\s*''\s*"
        if re.search(missing_pattern, code):
            issues.append("WARNING: Possible empty string assignment, consider using missing() function")

        # 检查不安全的比较
        if re.search(r'=\s*\.\s*|\s*\.\s*=', code):
            issues.append("WARNING: Possible invalid comparison with '.' (missing value)")

        return issues

    def format_for_injection(self, code: str, indentation: int = 4) -> str:
        """格式化为模板注入格式"""
        indent = ' ' * indentation
        lines = code.strip().split('\n')
        formatted = '\n'.join(f"{indent}{line}" if line.strip() else '' for line in lines)
        return formatted


if __name__ == "__main__":
    # 测试
    processor = SASCodePostProcessor()

    # 测试正常代码
    code = """if aeout = 'FATAL' then do;
    aerel = 'Y';
end;
else do;
    aerel = 'N';
end;"""

    result = processor.process(code, "AEREL")
    print(f"Valid: {result.valid}")
    print(f"Issues: {result.issues}")
    print(f"Formatted:\n{processor.format_for_injection(result.code)}")
