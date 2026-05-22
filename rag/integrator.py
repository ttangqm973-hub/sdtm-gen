"""
RAG Integrator - RAG 与 IR Builder 集成

将 RAG 流水线集成到 IR 构建流程中，为 ai_required 变量生成代码。
"""

import json
from pathlib import Path
from typing import Optional

from ir.models import DomainIR, Variable
from rag.pipeline import RAGPipeline, create_pipeline
from rag.retriever import RetrievalResult


def _json_default(obj):
    """Convert non-serializable types (e.g. numpy scalars) for JSON export."""
    if hasattr(obj, "item"):
        return obj.item()
    if hasattr(obj, "__float__"):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class RAGIntegrator:
    """RAG 集成器 - 连接 IR Builder 和 RAG Pipeline"""

    def __init__(
        self,
        pipeline: RAGPipeline = None,
        variable_whitelist: list[str] = None,
        macro_whitelist: list[str] = None
    ):
        self.pipeline = pipeline or create_pipeline(use_mock_llm=True)
        self.variable_whitelist = variable_whitelist
        self.macro_whitelist = macro_whitelist

    def process_domain(self, domain_ir: DomainIR) -> DomainIR:
        """为 DomainIR 中所有 ai_required 变量生成代码"""
        ai_vars = [v for v in domain_ir.variables if v.generation == "ai_required"]

        if not ai_vars:
            domain_ir.ai_summary = {
                "total_ai_vars": 0,
                "generated": 0,
                "total_confidence": 1.0,
                "review_required": False
            }
            return domain_ir

        generated_count = 0
        total_confidence = 0.0

        for var in ai_vars:
            try:
                # 构建上下文
                context = self._build_context(var, domain_ir)

                # 构建白名单
                var_whitelist = self.variable_whitelist
                if var_whitelist is None:
                    var_whitelist = self._build_variable_whitelist(domain_ir)

                macro_whitelist = self.macro_whitelist
                if macro_whitelist is None:
                    macro_whitelist = self._build_macro_whitelist(domain_ir)

                # 调用 RAG 生成
                result = self.pipeline.generate_with_report(
                    variable_name=var.name,
                    algorithm=var.algorithm or "",
                    context=context,
                    variable_whitelist=var_whitelist,
                    macro_whitelist=macro_whitelist
                )

                # 后处理生成的代码
                from generator.sas_post_processor import SASCodePostProcessor
                post_processor = SASCodePostProcessor()
                processed = post_processor.process(result["generated_code"], var.name)

                if processed.fixes:
                    var.ai_warnings = var.ai_warnings + [
                        f"Post-process fix: {f}" for f in processed.fixes
                    ]

                # 更新变量
                var.ai_generated_code = processed.code
                var.ai_confidence = result["confidence"]
                var.ai_sources = result.get("sources", [])
                var.ai_warnings = var.ai_warnings + processed.issues

                generated_count += 1
                total_confidence += result["confidence"]

            except Exception as e:
                var.ai_generated_code = f"/* ERROR: {e} */"
                var.ai_confidence = 0.0
                var.ai_warnings = [str(e)]

        # 更新 DomainIR 的 AI 摘要
        domain_ir.ai_summary = {
            "total_ai_vars": len(ai_vars),
            "generated": generated_count,
            "total_confidence": total_confidence / max(generated_count, 1),
            "review_required": any(
                v.ai_confidence and v.ai_confidence < 0.8
                for v in ai_vars
            ),
            "variables": [
                {
                    "name": v.name,
                    "confidence": v.ai_confidence,
                    "warnings": v.ai_warnings
                }
                for v in ai_vars
            ]
        }

        return domain_ir

    def _build_context(self, var: Variable, domain_ir: DomainIR) -> dict:
        """构建生成上下文"""
        context = {
            "domain": domain_ir.domain,
            "domain_label": domain_ir.domain_label,
            "related_vars": [],
            "related_domains": [],
            "logic_type": "conditional_derivation"
        }

        if var.ai_context:
            context["related_vars"] = var.ai_context.get("related_vars", [])
            context["related_domains"] = var.ai_context.get("related_domains", [])
            context["logic_type"] = var.ai_context.get("logic_type", "conditional_derivation")

        # 补充域内变量
        domain_var_names = [v.name for v in domain_ir.variables]
        context["domain_variables"] = domain_var_names

        return context

    def _build_variable_whitelist(self, domain_ir: DomainIR) -> list[str]:
        """构建变量白名单"""
        whitelist = set()

        # 域内变量
        for v in domain_ir.variables:
            whitelist.add(v.name.upper())

        # SDTM 标准标识符
        whitelist.update([
            "STUDYID", "USUBJID", "DOMAIN", "SUBJID", "SITEID",
            "RFSTDTC", "RFENDTC"
        ])

        return sorted(whitelist)

    def _build_macro_whitelist(self, domain_ir: DomainIR) -> list[str]:
        """构建宏白名单"""
        whitelist = set()

        # 域引用的宏
        for ref in domain_ir.macro_refs:
            whitelist.add(ref.upper())

        # 常用宏
        whitelist.update([
            "DATE", "AACTDY", "MSDTM_ATTRIB", "SDTM_XPT", "MCHECKLOG",
            "PRE", "SETPATH", "_DATA_", "MACMISS", "DATE_TRUNC"
        ])

        return sorted(whitelist)

    def export_ai_report(self, domain_ir: DomainIR, output_dir: str) -> str:
        """导出 AI 生成报告"""
        output_path = Path(output_dir) / f"{domain_ir.domain}_ai_report.json"

        report = {
            "domain": domain_ir.domain,
            "domain_label": domain_ir.domain_label,
            "ai_summary": domain_ir.ai_summary,
            "generated_code": {}
        }

        for var in domain_ir.variables:
            if var.ai_generated_code:
                report["generated_code"][var.name] = {
                    "code": var.ai_generated_code,
                    "confidence": var.ai_confidence,
                    "warnings": var.ai_warnings,
                    "sources": var.ai_sources
                }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=_json_default)

        return str(output_path)


def process_domain_with_rag(
    domain_ir: DomainIR,
    pipeline: RAGPipeline = None,
    variable_whitelist: list[str] = None,
    macro_whitelist: list[str] = None
) -> DomainIR:
    """便捷函数：使用 RAG 处理 DomainIR"""
    integrator = RAGIntegrator(
        pipeline=pipeline,
        variable_whitelist=variable_whitelist,
        macro_whitelist=macro_whitelist
    )
    return integrator.process_domain(domain_ir)


if __name__ == "__main__":
    # 测试
    from ir.models import Variable, DomainIR

    # 创建一个测试 DomainIR
    domain_ir = DomainIR(
        domain="AE",
        domain_label="Adverse Events",
        source_sheet="AE",
        variables=[
            Variable(
                seq=1,
                name="STUDYID",
                label="Study Identifier",
                type="Char",
                length=200,
                origin="Assigned",
                generation="template"
            ),
            Variable(
                seq=2,
                name="AEREL",
                label="Causality",
                type="Char",
                length=1,
                origin="Derived",
                generation="ai_required",
                algorithm="若 AEOUT='FATAL' 则 AEREL='Y'；若合并用药在30天内则 AEREL='P'",
                ai_context={
                    "related_vars": ["AEOUT", "CMDOSE", "CMSTDTC"],
                    "related_domains": ["CM"],
                    "logic_type": "conditional_derivation"
                }
            )
        ]
    )

    integrator = RAGIntegrator()
    result = integrator.process_domain(domain_ir)

    print(f"Domain: {result.domain}")
    print(f"AI Summary: {result.ai_summary}")
    for v in result.variables:
        if v.ai_generated_code:
            print(f"\n{v.name}:")
            print(f"  Code: {v.ai_generated_code}")
            print(f"  Confidence: {v.ai_confidence}")
