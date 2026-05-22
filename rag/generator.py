"""
Generator - LLM 代码生成器

基于检索结果生成 SAS 衍生变量代码。
"""

import os
import re
from typing import Optional
from dataclasses import dataclass

from rag.retriever import RetrievalResult

# SAS keywords/procedures excluded from variable validation
_SAS_KEYWORDS = frozenset({
    'IF', 'THEN', 'ELSE', 'DO', 'END', 'AND', 'OR', 'NOT', 'IN',
    'DATA', 'SET', 'MERGE', 'BY', 'WHERE', 'KEEP', 'DROP', 'RENAME',
    'LENGTH', 'FORMAT', 'INFORMAT', 'LABEL', 'ATTRIB', 'RETAIN',
    'INPUT', 'PUT', 'RETURN', 'OUTPUT', 'RUN', 'QUIT', 'STOP',
    'PROC', 'SELECT', 'WHEN', 'OTHERWISE', 'CALL', 'MISSING',
    'SORT', 'SQL', 'MEANS', 'FREQ', 'TRANSPOSE', 'DATASETS',
    'CONTENTS', 'PRINT', 'REPORT', 'TABULATE', 'COMPARE', 'COPY',
    'DELETE', 'APPEND', 'MODIFY', 'IMPORT', 'EXPORT', 'NODUPKEY',
    'FIRST', 'LAST', 'USUBJID', 'STUDYID', 'DOMAIN',
    'CMISS', 'N', 'NMISS', 'SUM', 'MEAN', 'MIN', 'MAX', 'STD',
    'STRIP', 'SCAN', 'CAT', 'CATX', 'CATS', 'TRIM', 'TRIMN',
    'UPCASE', 'LOWCASE', 'PROPCASE', 'COMPRESS', 'TRANWRD',
    'SUBSTR', 'INDEX', 'FIND', 'LENGTH', 'REVERSE', 'ANYALPHA',
    'ANYDIGIT', 'ANYSPACE', 'NOTALPHA', 'NOTDIGIT',
    'PUT', 'INPUT', 'INT', 'ROUND', 'CEIL', 'FLOOR', 'ABS', 'MOD',
    'LOG', 'LOG10', 'EXP', 'SQRT',
    'YMD', 'MDY', 'DATE', 'TODAY', 'DATETIME', 'TIME',
    'YYMMDD', 'DDMMYY', 'MMDDYY', 'DATE9', 'DATETIME19',
    'FIRST_DOT', 'LAST_DOT',
    'TITLE', 'FOOTNOTE', 'OPTIONS', 'LIBNAME', 'FILENAME',
    'GLOBAL', 'LOCAL', 'MACRO', 'MEND', 'SYSEVALF', 'SYSFUNC',
    'BQUOTE', 'NRBQUOTE', 'NRSTR', 'SUPERQ', 'UNQUOTE',
    'DOLLAR', 'PERCENT', 'COMMA', 'BEST',
    'Y', 'N', 'YES', 'NO',
})


@dataclass
class GenerationResult:
    """生成结果"""
    code: str
    confidence: float
    sources: list[str]
    warnings: list[str]
    explanation: str


class CodeGenerator:
    """SAS 代码生成器 — 基于 LLM API 的真实代码生成"""

    SYSTEM_PROMPT = (
        "你是 SDTM/ADaM 领域的 SAS 编程专家，精通 CDISC 标准。"
        "你的任务是生成符合 SDTM 规范的 SAS DATA 步代码。"
        "代码必须简洁、正确，处理缺失值，使用标准 SAS 语法。"
        "只输出代码和简要说明，不添加冗余注释。"
    )

    def __init__(self, model: str = None):
        self.model = model or os.getenv("CLAI_MODEL", "claude-sonnet-4-20250514")
        self._client = None

    def _check_api_key(self):
        """校验 API Key 是否已设置"""
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY 环境变量未设置。"
                "请设置环境变量或创建 .env 文件：ANTHROPIC_API_KEY=sk-..."
            )

    @property
    def client(self):
        if self._client is None:
            self._check_api_key()
            from anthropic import Anthropic
            self._client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

    def generate(
        self,
        variable_name: str,
        algorithm: str,
        context: dict,
        retrieved_chunks: list[RetrievalResult],
        variable_whitelist: list[str] = None,
        macro_whitelist: list[str] = None
    ) -> GenerationResult:
        """生成衍生变量代码（带重试）"""
        self._check_api_key()

        # 构建 prompt
        prompt = self._build_prompt(
            variable_name=variable_name,
            algorithm=algorithm,
            context=context,
            retrieved_chunks=retrieved_chunks
        )

        # 调用 LLM（带重试）
        generated_text = self._call_llm_with_retry(prompt)

        # 解析结果
        code = self._extract_code(generated_text)
        explanation = self._extract_explanation(generated_text)

        # 验证
        warnings = []
        if variable_whitelist:
            warnings.extend(self._validate_variables(code, variable_whitelist))
        if macro_whitelist:
            warnings.extend(self._validate_macros(code, macro_whitelist))

        # 置信度评估
        confidence = self._estimate_confidence(
            code=code,
            retrieved_chunks=retrieved_chunks,
            warnings=warnings
        )

        return GenerationResult(
            code=code,
            confidence=confidence,
            sources=[c.id for c in retrieved_chunks[:3]],
            warnings=warnings,
            explanation=explanation
        )

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """调用 LLM 并自动重试"""
        import time
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                # 可重试错误
                retryable = any(k in error_msg for k in [
                    "timeout", "connection", "rate limit", "overloaded",
                    "temporarily unavailable", "service unavailable"
                ])
                if not retryable or attempt == max_retries:
                    raise RuntimeError(
                        f"LLM API 调用失败 (尝试 {attempt}/{max_retries}): {e}"
                    ) from e
                wait = 2 ** attempt  # 指数退避: 2, 4, 8 秒
                time.sleep(wait)
        raise RuntimeError(f"LLM API 调用失败: {last_error}")

    def _build_prompt(
        self,
        variable_name: str,
        algorithm: str,
        context: dict,
        retrieved_chunks: list[RetrievalResult]
    ) -> str:
        """构建生成 Prompt（支持 token 安全截断）"""
        domain = context.get("domain", "unknown")
        related_vars = context.get("related_vars", [])
        related_domains = context.get("related_domains", [])

        # 构建参考代码（最多 3 个 chunks，每个最多 300 字符）
        reference_code = ""
        if retrieved_chunks:
            reference_code = "\n\n## 参考代码\n\n"
            for i, chunk in enumerate(retrieved_chunks[:3], 1):
                content = chunk.content[:300]
                if len(chunk.content) > 300:
                    content += " ..."
                source = chunk.metadata.get("source", "unknown")
                reference_code += f"### 参考 {i} (来源: {source})\n"
                reference_code += f"```sas\n{content}\n```\n\n"

        prompt = f"""## 任务
为变量 `{variable_name}` 生成 SAS 代码实现以下算法：
{algorithm}

## 上下文
- 域: {domain}
- 相关变量: {', '.join(related_vars) if related_vars else '无'}
- 跨域引用: {', '.join(related_domains) if related_domains else '无'}
{reference_code}

## 要求
1. 生成符合 CDISC SDTM 标准的 SAS DATA 步代码
2. 使用 IF-THEN-ELSE 或 SELECT-WHEN 结构
3. 处理缺失值情况（cmiss/missing）
4. 变量名使用大写
5. 代码必须在 DATA 步中使用

## 输出格式
### 代码
```sas
/* 你的代码 */
```

### 说明
简要说明实现逻辑。
"""
        return prompt

    def _extract_code(self, text: str) -> str:
        """从生成文本中提取代码（支持多种围栏格式）"""
        # 尝试 sas/SAS/saslog 标签
        for tag in [r'sas', r'SAS', r'saslog']:
            pattern = rf'```{tag}\s*(.*?)\s*```'
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                return matches[0].strip()

        # 尝试无标签围栏
        pattern = r'```\s*(.*?)\s*```'
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()

        # 兜底：去除说明部分，只保留第一个代码块之前的文本
        lines = text.splitlines()
        code_lines = []
        in_code = False
        for line in lines:
            if '```' in line:
                in_code = not in_code
                continue
            if in_code or (line.strip() and not line.strip().startswith('#')):
                code_lines.append(line)
        if code_lines:
            return '\n'.join(code_lines).strip()

        return text.strip()

    def _extract_explanation(self, text: str) -> str:
        """提取说明文本"""
        pattern = r'### 说明\s*(.*?)(?=###|```|$)'
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()
        return ""

    def _validate_variables(self, code: str, whitelist: list[str]) -> list[str]:
        """验证代码中的变量是否在白名单中"""
        warnings = []
        whitelist_upper = set(v.upper() for v in whitelist)

        # Strip comments and string literals to avoid false positives
        clean = self._strip_sas_noise(code).upper()

        pattern = r'\b([A-Z][A-Z0-9_]*)\b'
        found_vars = set(re.findall(pattern, clean))

        unknown_vars = found_vars - whitelist_upper - _SAS_KEYWORDS
        for var in unknown_vars:
            warnings.append(f"变量 {var} 不在白名单中，请确认是否正确")

        return warnings

    @staticmethod
    def _strip_sas_noise(code: str) -> str:
        """Remove comments and string literals from SAS code for validation."""
        # Remove block comments /* ... */
        code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.DOTALL)
        # Remove line comments * ... ;
        code = re.sub(r'(?m)^\s*\*[^;]*;', ' ', code)
        # Remove single-quoted strings
        code = re.sub(r"'[^']*'", "''", code)
        # Remove double-quoted strings
        code = re.sub(r'"[^"]*"', '""', code)
        return code

    def _validate_macros(self, code: str, whitelist: list[str]) -> list[str]:
        """验证代码中的宏是否在白名单中"""
        warnings = []
        whitelist_upper = set(m.upper() for m in whitelist)

        # 提取宏调用
        pattern = r'%(\w+)'
        found_macros = set(re.findall(pattern, code.upper()))

        unknown_macros = found_macros - whitelist_upper
        for macro in unknown_macros:
            warnings.append(f"宏 %{macro} 不在白名单中，请确认是否存在")

        return warnings

    def _estimate_confidence(
        self,
        code: str,
        retrieved_chunks: list[RetrievalResult],
        warnings: list[str]
    ) -> float:
        """估算置信度（基于代码结构完整性）"""
        base_score = 0.65

        # 检索质量影响
        if retrieved_chunks:
            avg_score = sum(c.score for c in retrieved_chunks[:3]) / min(len(retrieved_chunks), 3)
            base_score += avg_score * 0.15

        code_lower = code.lower()

        # 结构完整性加分
        if "data " in code_lower and "run;" in code_lower:
            base_score += 0.05
        if "if" in code_lower and "then" in code_lower:
            base_score += 0.03
        if "else" in code_lower:
            base_score += 0.02
        if "proc sort" in code_lower and "run;" in code_lower:
            base_score += 0.03
        if "select (" in code_lower and "end;" in code_lower:
            base_score += 0.03
        if "cmiss(" in code_lower or "missing(" in code_lower:
            base_score += 0.02

        # 警告扣分
        base_score -= len(warnings) * 0.04

        return min(0.95, max(0.30, base_score))


class MockGenerator(CodeGenerator):
    """Mock 生成器 — 基于模板驱动的 SAS 代码生成，无需 LLM API"""

    def generate(
        self,
        variable_name: str,
        algorithm: str,
        context: dict,
        retrieved_chunks: list[RetrievalResult],
        variable_whitelist: list[str] = None,
        macro_whitelist: list[str] = None
    ) -> GenerationResult:
        code, template_name, confidence = self._template_generate(
            variable_name, algorithm, context, retrieved_chunks
        )

        warnings = []
        if variable_whitelist:
            warnings.extend(self._validate_variables(code, variable_whitelist))
        if macro_whitelist:
            warnings.extend(self._validate_macros(code, macro_whitelist))

        sources = [c.id for c in retrieved_chunks[:3]]
        if retrieved_chunks:
            sources += [c.id for c in retrieved_chunks if c.metadata.get("source")]

        return GenerationResult(
            code=code,
            confidence=confidence,
            sources=sources[:5],
            warnings=warnings,
            explanation=f"模板驱动生成 ({template_name}): {variable_name} 衍生逻辑"
        )

    # ------------------------------------------------------------------
    # Template system
    # ------------------------------------------------------------------

    def _template_generate(
        self, variable_name: str, algorithm: str, context: dict,
        retrieved_chunks: list[RetrievalResult]
    ) -> tuple[str, str, float]:
        algo = algorithm
        algo_l = algorithm.lower()
        domain = context.get("domain", "")
        related = context.get("related_vars", [])
        related_domains = context.get("related_domains", [])

        candidate = self._pick_best_template(algo_l, context, retrieved_chunks)
        if candidate:
            code = candidate["render"](
                var_name=variable_name, algorithm=algorithm, algo_lower=algo_l,
                domain=domain, related_vars=related,
                related_domains=related_domains, context=context,
                chunks=retrieved_chunks
            )
            return code, candidate["name"], self._score_to_confidence(candidate, retrieved_chunks)

        # Fallback: generic comment + null assignment
        return (
            f"/* TODO: Implement {variable_name} derivation */\n"
            f"/* Algorithm: {algorithm[:120]} */\n"
            f"{variable_name} = '';",
            "fallback",
            0.35
        )

    def _pick_best_template(
        self, algo_l: str, context: dict, chunks: list[RetrievalResult]
    ) -> dict | None:
        best_score = 0.0
        best = None
        for tmpl in _TEMPLATES:
            score = sum(1.0 for kw in tmpl["keywords"] if kw in algo_l)
            score += sum(0.5 for rx in tmpl.get("patterns", []) if rx.search(algo_l))
            # 额外加分：如果 related_domains 非空且模板支持跨域
            if context.get("related_domains") and tmpl["name"] == "cross_domain_lookup":
                score += 2.0
            if score > best_score:
                best_score = score
                best = tmpl
        return best

    def _score_to_confidence(self, template: dict, chunks: list[RetrievalResult]) -> float:
        base = 0.55
        if chunks:
            avg = sum(c.score for c in chunks[:3]) / min(len(chunks), 3)
            base += avg * 0.15
        base += template.get("confidence_boost", 0.0)
        return min(0.85, max(0.30, base))


# ------------------------------------------------------------------
# Template definitions
# ------------------------------------------------------------------

import re as _re  # noqa: E402 (keep imports grouped if possible)


def _extract_condition_parts(algorithm: str) -> list[tuple[str, str]]:
    """Extract 'condition → value' pairs from Chinese/English algorithm text.
    Handles: 若 X='A' 则 Y='B';   if X='A' then Y='B';
             X='A' 则 Y='B';      X='A' then Y='B'
    """
    pairs = []
    # 正向：若 CONDITION 则 VALUE
    fwd = _re.compile(
        r'(?:若\s*|if\s+)?(.+?)\s*(?:则|then)\s*(.+)',
        _re.IGNORECASE
    )
    # 反向：VALUE if/when CONDITION
    rev = _re.compile(
        r'["\']?([^"\']+)["\']?\s+(?:if|when)\s+(.+)',
        _re.IGNORECASE
    )
    clauses = _re.split(r'[;；]\s*', algorithm)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        m = fwd.search(clause)
        if m:
            pairs.append((m.group(1).strip(), m.group(2).strip()))
            continue
        m = rev.search(clause)
        if m:
            pairs.append((m.group(2).strip(), m.group(1).strip()))
    return pairs


def _find_date_source_var(algorithm: str, related_vars: list[str]) -> str:
    """Find the most likely source DTC variable for a date derivation."""
    dtc_vars = _re.findall(r'\b([A-Z]{1,8}DTC)\b', algorithm.upper())
    if dtc_vars:
        return dtc_vars[0]
    for v in related_vars:
        if v.upper().endswith("DTC"):
            return v
    return "RFSTDTC"


def _quote_if_char(value: str) -> str:
    """Wrap value in single quotes unless it's numeric."""
    v = value.strip().strip("'\"")
    try:
        float(v)
        return v
    except ValueError:
        return f"'{v}'"


_TEMPLATES = [
    {
        "name": "iso_date_parse",
        "keywords": ["dtc", "date", "日期", "datetime", "yymmdd", "is8601",
                     "e8601dt", "datepart", "date9"],
        "patterns": [_re.compile(r'(?i)\b[rd][fi]?[sa]?\w?dtc\b'),
                     _re.compile(r'(?i)yymmdd|date9|is8601|e8601dt')],
        "confidence_boost": 0.10,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            f"/* {var_name}: ISO 8601 date derivation */\n"
            f"format {var_name} date9.;\n"
            f"{var_name} = input(strip(scan({_find_date_source_var(algorithm, related_vars)}, 1, 'T')), ??yymmdd10.);"
        ),
    },
    {
        "name": "conditional_assignment",
        "keywords": ["若", "则", "then", "if ", "when", "条件", "否则", "else",
                     "赋值"],
        "patterns": [_re.compile(r'(?i)(若|则|then|else|否则)')],
        "confidence_boost": 0.05,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            _render_conditional(var_name, algorithm, related_vars)
        ),
    },
    {
        "name": "flag_derivation",
        "keywords": ["fl", "flag", "set to", "y/n", "yn", "标记", "标志",
                     "saffl", "ittfl", "efffl", "enrlfl"],
        "patterns": [_re.compile(r'(?i)\b[YSEN]\s*/\s*[N]\b'),
                     _re.compile(r'(?i)set\s+to\s+[\'"]?Y[\'"]?'),
                     _re.compile(r'(?i)([A-Z]{2,6}FL)\b')],
        "confidence_boost": 0.08,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            _render_flag(var_name, algorithm, domain, related_vars)
        ),
    },
    {
        "name": "categorical_mapping",
        "keywords": ["decode", "codelist", "select", "when", "otherwise",
                     "编码", "映射", "字典", "值="],
        "patterns": [_re.compile(r'(?i)(select|when|otherwise|codelist)'),
                     _re.compile(r'[A-Z]+=[一-鿿\w]+')],
        "confidence_boost": 0.06,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            _render_mapping(var_name, algorithm, related_vars)
        ),
    },
    {
        "name": "numeric_computation",
        "keywords": ["compute", "calculate", "+", "-", "*", "/", "计算",
                     "age", "bmi", "yrsdx", "sfum"],
        "patterns": [_re.compile(r'(?i)\b(age|bmi|bsa|weight|height)\b'),
                     _re.compile(r'[+\-*/]')],
        "confidence_boost": 0.04,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            _render_numeric(var_name, algorithm, related_vars, domain)
        ),
    },
    {
        "name": "study_day",
        "keywords": ["dy", "study day", "aactdy", "day", "研究日", "天"],
        "patterns": [_re.compile(r'(?i)\b([A-Z]{2,7}DY)\b'),
                     _re.compile(r'(?i)study.?day|aactdy')],
        "confidence_boost": 0.08,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            _render_study_day(var_name, algorithm, related_vars)
        ),
    },
    {
        "name": "baseline_flag",
        "keywords": ["baseline", "blfl", "baseflag", "abifl", "ablfl",
                     "基线", "last before", "last non-missing"],
        "patterns": [_re.compile(r'(?i)\b([A-Z]{2,7}BLFL)\b'),
                     _re.compile(r'(?i)baseline|baseflag|ablfl')],
        "confidence_boost": 0.10,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            _render_baseline_flag(var_name, algorithm, domain, related_vars)
        ),
    },
    {
        "name": "first_last_by_group",
        "keywords": ["first.", "last.", "by usubjid", "first", "last",
                     "最早", "最晚", "initial", "latest"],
        "patterns": [_re.compile(r'(?i)(first\.|last\.|by\s+usubjid)')],
        "confidence_boost": 0.06,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            _render_first_last(var_name, algorithm, domain, related_vars)
        ),
    },
    {
        "name": "cross_domain_lookup",
        "keywords": ["merge", "lookup", "跨域", "合并", "关联", "引用",
                     "来自", "from other", "supp", "sdtm", "predecessor",
                     "来自其他域"],
        "patterns": [_re.compile(r'(?i)(merge|lookup|supp|跨域|合并)'),
                     _re.compile(r'(?i)\b([A-Z]{2,4})\.([A-Z]{2,6})\b')],
        "confidence_boost": 0.08,
        "render": lambda var_name, algorithm, algo_lower, domain, related_vars,
                         related_domains, context, chunks: (
            _render_cross_domain(var_name, algorithm, domain,
                                 related_vars, related_domains)
        ),
    },
]


def _render_conditional(var_name: str, algorithm: str, related: list[str]) -> str:
    pairs = _extract_condition_parts(algorithm)
    source_var = related[0] if related else "SOURCE"
    lines = [f"/* {var_name}: conditional derivation */"]
    lines.append(f"length {var_name} $200.;")
    if pairs:
        for i, (cond, val) in enumerate(pairs):
            cond_clean = cond.strip().strip(";；")
            val_clean = _quote_if_char(val.strip().strip(";；"))
            if i == 0:
                lines.append(f"if {cond_clean} then {var_name} = {val_clean};")
            else:
                lines.append(f"else if {cond_clean} then {var_name} = {val_clean};")
        lines.append(f"else {var_name} = '';")
    else:
        lines.append(f"if {source_var} = 'Y' then {var_name} = '{var_name}_YES';")
        lines.append(f"else if {source_var} = 'N' then {var_name} = '{var_name}_NO';")
        lines.append(f"else {var_name} = '';")
    return "\n".join(lines)


def _render_flag(var_name: str, algorithm: str, domain: str, related: list[str]) -> str:
    lines = [f"/* {var_name} flag */"]
    if related:
        condition = f"{related[0]} > .z"
    elif "date" in algorithm.lower() or "dtc" in algorithm.lower():
        condition = "not missing(TRTSDT)"
    else:
        condition = "not missing(USUBJID)"
    lines.append(f"if {condition} then {var_name} = 'Y';")
    lines.append(f"else {var_name} = 'N';")
    return "\n".join(lines)


def _render_mapping(var_name: str, algorithm: str, related: list[str]) -> str:
    source = related[0] if related else "RAW_VAR"
    lines = [f"/* {var_name}: categorical mapping */"]
    lines.append(f"select ({source});")
    pairs = _re.findall(r"(\w+)\s*=\s*([一-鿿\w]+)", algorithm)
    if pairs:
        for code, decode in pairs[:10]:
            lines.append(f'    when ("{code}") {var_name} = "{decode}";')
    else:
        lines.append(f'    when ("Y") {var_name} = "Yes";')
        lines.append(f'    when ("N") {var_name} = "No";')
    lines.append(f"    otherwise {var_name} = {source};")
    lines.append("end;")
    return "\n".join(lines)


def _render_numeric(var_name: str, algorithm: str, related: list[str], domain: str) -> str:
    lines = [f"/* {var_name}: numeric computation */"]
    if "age" in var_name.lower() or "age" in algorithm.lower():
        lines.append(f"if cmiss(BRTHDT, TRTSDT) = 0 then {var_name} = round((TRTSDT - BRTHDT + 1) / 365.25, 0.01);")
    elif "sfum" in var_name.lower() or "sfum" in algorithm.lower():
        lines.append(f"if cmiss(DTHDT, TRTSDT) = 0 then {var_name} = (DTHDT - TRTSDT + 1) / 30.4375;")
    elif "bmi" in var_name.lower():
        lines.append(f"if cmiss(WEIGHTBL, HEIGHTBL) = 0 and HEIGHTBL > 0 then {var_name} = WEIGHTBL / (HEIGHTBL / 100) ** 2;")
    elif "yrsdx" in var_name.lower():
        lines.append(f"if cmiss(DIAGDT, TRTSDT) = 0 then {var_name} = round((TRTSDT - DIAGDT + 1) / 365.25, 0.01);")
    else:
        operand_a = related[0] if len(related) > 0 else "VAL_A"
        operand_b = related[1] if len(related) > 1 else "VAL_B"
        lines.append(f"if cmiss({operand_a}, {operand_b}) = 0 then {var_name} = {operand_a} - {operand_b};")
    return "\n".join(lines)


def _render_study_day(var_name: str, algorithm: str, related: list[str]) -> str:
    dtc_var = _find_date_source_var(algorithm, related)
    lines = [f"/* {var_name}: study day from {dtc_var} */"]
    dtc_date = dtc_var.replace("DTC", "DT") if "DTC" in dtc_var else f"{dtc_var}_DT"
    lines.append(f"format {dtc_date} date9.;")
    lines.append(f"{dtc_date} = input(strip(scan({dtc_var}, 1, 'T')), ??yymmdd10.);")
    lines.append(f"/* Compute study day relative to first treatment date */")
    lines.append(f"if cmiss({dtc_date}, RFSTDT) = 0 then do;")
    lines.append(f"    if {dtc_date} >= RFSTDT then {var_name} = {dtc_date} - RFSTDT + 1;")
    lines.append(f"    else {var_name} = {dtc_date} - RFSTDT;")
    lines.append(f"end;")
    return "\n".join(lines)


def _render_baseline_flag(var_name: str, algorithm: str, domain: str, related: list[str]) -> str:
    last_var = related[0] if related else "VISITNUM"
    lines = [f"/* {var_name}: baseline flag — last non-missing before treatment */"]
    lines.append(f"proc sort data=sdtm.{domain.lower()} out=_{domain.lower()}_bl;")
    lines.append(f"    by USUBJID {last_var} VISITNUM;")
    lines.append(f"    where not missing({last_var}) and VISITNUM <= 0;")
    lines.append(f"run;")
    lines.append(f"")
    lines.append(f"data _{domain.lower()}_bl2;")
    lines.append(f"    set _{domain.lower()}_bl;")
    lines.append(f"    by USUBJID;")
    lines.append(f"    if last.USUBJID then {var_name} = 'Y';")
    lines.append(f"    keep USUBJID {var_name};")
    lines.append(f"run;")
    return "\n".join(lines)


def _render_first_last(var_name: str, algorithm: str, domain: str, related: list[str]) -> str:
    lines = [f"/* {var_name}: first/last by-group derivation */"]
    # 避免 sort_keys 中重复 USUBJID
    sort_extra = [r for r in (related[:2] if related else ["DTC"]) if r.upper() != "USUBJID"]
    sort_keys = "USUBJID " + " ".join(sort_extra) if sort_extra else "USUBJID"
    lines.append(f"proc sort data=sdtm.{domain.lower()} out=_{domain.lower()}_by;")
    lines.append(f"    by {sort_keys};")
    lines.append(f"run;")
    lines.append(f"")
    first_var = related[0] if related else "DTC"
    lines.append(f"data _{domain.lower()}_fl;")
    lines.append(f"    set _{domain.lower()}_by;")
    lines.append(f"    by USUBJID;")
    # 仅对日期变量加 date9. 格式
    if "dt" in var_name.lower() or "date" in algorithm.lower():
        lines.append(f"    format {var_name} date9.;")
    lines.append(f"    if first.USUBJID then {var_name} = input(strip(scan({first_var}, 1, 'T')), ??yymmdd10.);")
    lines.append(f"    retain {var_name};")
    lines.append(f"    if first.USUBJID;")
    lines.append(f"    keep USUBJID {var_name};")
    lines.append(f"run;")
    return "\n".join(lines)


def _render_cross_domain(var_name: str, algorithm: str, domain: str,
                         related_vars: list[str], related_domains: list[str]) -> str:
    ref_domain = related_domains[0].upper() if related_domains else "CM"
    ref_var = related_vars[0] if related_vars else "VAR"
    lines = [f"/* {var_name}: cross-domain lookup from {ref_domain} */"]
    lines.append(f"proc sort data=sdtm.{ref_domain.lower()} out=_{ref_domain.lower()}_lkp;")
    lines.append(f"    by USUBJID;")
    lines.append(f"    where not missing({ref_var});")
    lines.append(f"run;")
    lines.append(f"")
    lines.append(f"proc sort data=_{domain.lower()}_base out=_{domain.lower()}_base_s;")
    lines.append(f"    by USUBJID;")
    lines.append(f"run;")
    lines.append(f"")
    lines.append(f"data _{domain.lower()}_merged;")
    lines.append(f"    merge _{domain.lower()}_base_s(in=a) _{ref_domain.lower()}_lkp(in=b keep=USUBJID {ref_var});")
    lines.append(f"    by USUBJID;")
    lines.append(f"    if a;")
    lines.append(f"    {var_name} = {ref_var};")
    lines.append(f"run;")
    return "\n".join(lines)


def get_generator(model: str = None, use_mock: bool = False) -> CodeGenerator:
    """获取生成器实例"""
    if use_mock:
        return MockGenerator()
    return CodeGenerator(model or "claude-sonnet-4-20250514")


if __name__ == "__main__":
    # 测试 Mock 生成器
    gen = get_generator(use_mock=True)
    result = gen.generate(
        variable_name="AEREL",
        algorithm="若 AEOUT='FATAL' 则 AEREL='Y'",
        context={"domain": "AE"},
        retrieved_chunks=[]
    )
    print(f"Code:\n{result.code}")
    print(f"Confidence: {result.confidence}")
