import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from batch.study_config import StudyConfig
from generator.sas_generator import SASGenerator
from ir.models import DomainIR
from lint.sas_linter import SASLinter
from parser.excel_reader import ExcelReader
from parser.ir_builder import IRBuilder


SDTM_DOMAINS = {
    'AE', 'CM', 'LB', 'VS', 'EX', 'MH', 'EG', 'PE',
    'DS', 'SV', 'IE', 'QS', 'RS', 'TR', 'TU', 'PR', 'FA',
    'CO', 'DD', 'DV', 'SE', 'SS', 'SU', 'RELREC', 'TRIAL',
    'PC', 'IS', 'PF', 'CV', 'XO', 'MI', 'EC', 'TA', 'TE',
    'TD', 'TI', 'TS', 'TV', 'DM'
}


def _is_variable_sheet(rows: list[dict]) -> bool:
    """检查是否包含 SPEC 变量定义（过滤辅助表）"""
    if not rows:
        return False
    first_row = rows[0]
    var_indicators = ['varname', 'variable', 'varlabel', 'label']
    keys_lower = {k.lower() for k in first_row.keys()}
    match_count = sum(1 for ind in var_indicators if any(ind in k for k in keys_lower))
    return match_count >= 2


class BatchScheduler:
    """批量调度引擎：一次处理整个 Study 的全部域"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.reader = ExcelReader()
        self.builder = IRBuilder()

    def run(
        self,
        spec_file: str,
        config: StudyConfig,
        progress_callback: Optional[Callable[[str, str, int, int], None]] = None,
    ) -> dict:
        """执行批量生成，返回报告字典"""
        start_time = time.time()
        start_iso = datetime.now().isoformat()

        # 读取 SPEC
        sheets = self.reader.read(spec_file)

        # 过滤有效域 sheet
        domains_to_process = []
        for sheet_name, rows in sheets.items():
            if not _is_variable_sheet(rows):
                continue
            actual_domain = self._resolve_domain(sheet_name, spec_file)
            # 如果 config.domains 不为空，只处理指定的域
            if config.domains and actual_domain.upper() not in {d.upper() for d in config.domains}:
                continue
            domains_to_process.append((actual_domain, rows))

        # 准备输出目录
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 RAG
        rag_pipeline = None
        if config.rag_enabled:
            rag_pipeline = self._init_rag(config)

        # 初始化 Linter
        linter = SASLinter() if config.lint_enabled else None

        # 并发生成
        generator = SASGenerator(str(output_dir))
        results = []
        completed_count = 0
        total_count = len(domains_to_process)

        if len(domains_to_process) == 1:
            # 单域不需要线程池
            domain, rows = domains_to_process[0]
            result = self._process_domain(
                domain, rows, generator, rag_pipeline, linter, config
            )
            results.append(result)
            completed_count += 1
            if progress_callback:
                progress_callback("progress", domain, completed_count, total_count)
        else:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(
                        self._process_domain,
                        domain, rows, generator, rag_pipeline, linter, config
                    ): domain
                    for domain, rows in domains_to_process
                }
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    completed_count += 1
                    if progress_callback:
                        progress_callback("progress", result["domain"], completed_count, total_count)

        # 汇总报告
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        generated_files = [r["output_file"] for r in results if r.get("output_file")]

        end_time = time.time()
        end_iso = datetime.now().isoformat()

        report = {
            "study_name": config.study_name,
            "spec_file": spec_file,
            "total_domains": len(domains_to_process),
            "successful": successful,
            "failed": failed,
            "start_time": start_iso,
            "end_time": end_iso,
            "elapsed_seconds": round(end_time - start_time, 2),
            "generated_files": generated_files,
            "details": results,
        }

        # 写入 batch_report.json
        batch_report_path = output_dir / f"{config.study_name}_batch_report.json"
        with open(batch_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        report["batch_report_path"] = str(batch_report_path)
        return report

    def _resolve_domain(self, sheet_name: str, spec_file: str) -> str:
        """从 sheet 名或文件名推断 SDTM 域"""
        if sheet_name.upper() in SDTM_DOMAINS:
            return sheet_name.upper()
        # 尝试从文件名推断
        filename = os.path.basename(spec_file).split('.')[0].upper()
        if filename in SDTM_DOMAINS:
            return filename
        # 尝试去掉 _spec 后缀
        filename_clean = filename.replace("_SPEC", "").replace("_spec", "")
        if filename_clean in SDTM_DOMAINS:
            return filename_clean
        return sheet_name.upper()

    def _init_rag(self, config: StudyConfig):
        """初始化 RAG 流水线"""
        try:
            from rag import create_pipeline
            kb_path = config.kb_path or "D:/Claude code/Knowlegde base"
            pipeline = create_pipeline(
                knowledge_base_path=kb_path,
                use_mock_llm=config.rag_mock
            )
            # 确保知识库已构建
            if pipeline.vector_store.count() == 0:
                pipeline.build_knowledge_base()
            return pipeline
        except ImportError as e:
            if config.verbose:
                print(f"Warning: RAG module not available: {e}", file=sys.stderr)
            return None

    def _process_domain(
        self,
        domain: str,
        rows: list[dict],
        generator: SASGenerator,
        rag_pipeline,
        linter,
        config: StudyConfig
    ) -> dict:
        """处理单个域，返回结果字典"""
        result = {
            "domain": domain,
            "status": "pending",
            "output_file": None,
            "error": None,
            "lint_issues": [],
            "ai_summary": None,
        }

        try:
            domain_ir = self.builder.build(domain, rows)

            # 合并全局宏引用
            if config.global_macro_refs:
                existing = set(domain_ir.macro_refs)
                for ref in config.global_macro_refs:
                    if ref not in existing:
                        domain_ir.macro_refs.append(ref)

            # RAG 处理
            if rag_pipeline:
                ai_vars = [v for v in domain_ir.variables if v.generation == "ai_required"]
                if ai_vars:
                    from rag.integrator import RAGIntegrator
                    integrator = RAGIntegrator(pipeline=rag_pipeline)
                    domain_ir = integrator.process_domain(domain_ir)
                    result["ai_summary"] = domain_ir.ai_summary

                    # 导出 AI 报告
                    if domain_ir.ai_summary and domain_ir.ai_summary.get("generated", 0) > 0:
                        integrator.export_ai_report(domain_ir, generator.output_dir)

            # 生成 SAS 文件
            output_file = generator.generate(domain_ir)
            result["output_file"] = output_file
            result["status"] = "success"

            # Lint 检查
            if linter:
                lint_report = linter.lint_file(output_file)
                result["lint_issues"] = [
                    {
                        "line": i.line,
                        "column": i.column,
                        "severity": i.severity,
                        "message": i.message,
                    }
                    for i in lint_report.issues
                ]

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)

        return result
