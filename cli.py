import click
import os
import sys
from pathlib import Path

from parser.excel_reader import ExcelReader
from parser.ir_builder import IRBuilder
from generator.sas_generator import SASGenerator
from lint.sas_linter import SASLinter


@click.group()
@click.version_option(version="0.2.0", prog_name="sdtm-gen")
def cli():
    """SDTM SAS Code Generator - Generate SDTM domain SAS programs from SPEC files."""
    pass


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("-o", "--output", "output_dir", default=".", help="Output directory for generated SAS files")
@click.option("--lint", is_flag=True, help="Run L1 linter on generated code")
@click.option("--rag", "use_rag", is_flag=True, help="Use RAG pipeline for AI-required variable generation")
@click.option("--rag-mock", is_flag=True, help="Use mock LLM for RAG (testing only)")
@click.option("--kb-path", default=None, help="Knowledge base path (default: D:/Claude code/Knowlegde base)")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def generate(spec_file, output_dir, lint, use_rag, rag_mock, kb_path, verbose):
    """Generate SAS code from SPEC Excel/CSV file.

    SPEC_FILE: Path to the SPEC file (Excel .xlsx or CSV .csv)
    """
    if verbose:
        click.echo(f"Reading SPEC file: {spec_file}")

    reader = ExcelReader()
    try:
        sheets = reader.read(spec_file)
    except Exception as e:
        click.echo(f"Error reading SPEC file: {e}", err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"Found {len(sheets)} domain(s): {', '.join(sheets.keys())}")

    builder = IRBuilder()
    generator = SASGenerator(output_dir)
    linter = SASLinter() if lint else None

    # 初始化 RAG
    rag_pipeline = None
    if use_rag:
        # 真实 LLM 模式需检查 API Key
        if not rag_mock:
            if not os.getenv("ANTHROPIC_API_KEY"):
                click.echo(
                    "Error: ANTHROPIC_API_KEY not set. "
                    "Use --rag-mock for testing or set the env var.",
                    err=True
                )
                sys.exit(1)

        if verbose:
            click.echo("Initializing RAG pipeline...")
        try:
            from rag import create_pipeline

            kb_path = kb_path or "D:/Claude code/Knowlegde base"
            rag_pipeline = create_pipeline(
                knowledge_base_path=kb_path,
                use_mock_llm=rag_mock
            )
            if verbose:
                click.echo(f"RAG pipeline initialized (mock={rag_mock})")
        except ImportError as e:
            click.echo(f"Warning: RAG module not available: {e}", err=True)
            if verbose:
                click.echo("Falling back to template-only generation")
            use_rag = False

    os.makedirs(output_dir, exist_ok=True)

    # 从文件名推断域
    filename_domain = os.path.basename(spec_file).split('.')[0].upper()

    generated_files = []
    for domain, rows in sheets.items():
        # 跳过不含 SPEC 变量定义的 sheet（如 Values、Codelist 辅助表）
        if not _is_variable_sheet(rows):
            if verbose:
                click.echo(f"Skipping sheet '{domain}' (not a variable definition sheet)")
            continue

        # 如果 sheet 名不是有效的 SDTM 域，使用文件名域
        sdtm_domains = {'AE', 'DM', 'CM', 'LB', 'VS', 'EX', 'MH', 'EG', 'PE',
                        'DS', 'SV', 'IE', 'QS', 'RS', 'TR', 'TU', 'PR', 'FA',
                        'CO', 'DD', 'DV', 'SE', 'SS', 'SU', 'RELREC', 'TRIAL',
                        'PC', 'IS', 'PF', 'CV', 'XO', 'MI', 'EC', 'TA', 'TE',
                        'TD', 'TI', 'TS', 'TV'}
        actual_domain = domain if domain.upper() in sdtm_domains else filename_domain

        if not rows:
            continue

        if verbose:
            click.echo(f"\nProcessing domain: {actual_domain}")

        domain_ir = builder.build(actual_domain, rows)

        if verbose:
            template_vars = sum(1 for v in domain_ir.variables if v.generation == "template")
            ai_vars = sum(1 for v in domain_ir.variables if v.generation == "ai_required")
            click.echo(f"  Variables: {len(domain_ir.variables)} (template: {template_vars}, AI-required: {ai_vars})")

        # RAG 处理
        if use_rag and rag_pipeline:
            ai_vars = [v for v in domain_ir.variables if v.generation == "ai_required"]
            if ai_vars:
                if verbose:
                    click.echo(f"  Generating {len(ai_vars)} AI-required variable(s)...")

                # 确保知识库已构建
                if rag_pipeline.vector_store.count() == 0:
                    if verbose:
                        click.echo("  Building knowledge base...")
                    rag_pipeline.build_knowledge_base()

                from rag.integrator import RAGIntegrator
                integrator = RAGIntegrator(pipeline=rag_pipeline)
                domain_ir = integrator.process_domain(domain_ir)

                if verbose:
                    for v in domain_ir.variables:
                        if v.ai_generated_code:
                            status = "OK" if v.ai_confidence and v.ai_confidence >= 0.8 else "REVIEW"
                            click.echo(f"    {v.name}: confidence={v.ai_confidence:.2f} [{status}]")

                # 导出报告
                if domain_ir.ai_summary and domain_ir.ai_summary.get("generated", 0) > 0:
                    from rag.integrator import RAGIntegrator
                    integrator = RAGIntegrator(pipeline=rag_pipeline)
                    report_path = integrator.export_ai_report(domain_ir, output_dir)
                    if verbose:
                        click.echo(f"  AI report saved: {report_path}")

        output_file = generator.generate(domain_ir)
        generated_files.append(output_file)

        if verbose:
            click.echo(f"  Generated: {output_file}")

        if lint and linter:
            report = linter.lint_file(output_file)
            if report.issues:
                click.echo(f"\n  Lint issues for {domain}:")
                for issue in report.issues:
                    click.echo(f"    Line {issue.line}: [{issue.severity.upper()}] {issue.message}")
            else:
                click.echo(f"  No lint issues found")

    click.echo(f"\nGenerated {len(generated_files)} SAS file(s) in {output_dir}")
    for f in generated_files:
        click.echo(f"  - {f}")

    if use_rag and rag_pipeline:
        kb_stats = rag_pipeline.get_stats()
        click.echo(f"\nRAG knowledge base: {kb_stats.get('total_chunks', 'N/A')} chunks")


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("-o", "--output", "output_dir", default="output", help="Output directory for generated SAS files")
@click.option("--config", "config_path", default=None, help="Path to study config JSON file")
@click.option("--study-name", default=None, help="Study name (overrides config file)")
@click.option("--domains", default=None, help="Comma-separated domain list (overrides config file)")
@click.option("--rag", "use_rag", is_flag=True, help="Use RAG pipeline for AI-required variables")
@click.option("--rag-mock", is_flag=True, help="Use mock LLM for RAG (testing only)")
@click.option("--lint", is_flag=True, help="Run L1 linter on generated code")
@click.option("--kb-path", default=None, help="Knowledge base path")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def batch(spec_file, output_dir, config_path, study_name, domains, use_rag, rag_mock, lint, kb_path, verbose):
    """Batch generate SAS code for all domains in a SPEC file.

    SPEC_FILE: Path to the SPEC file (Excel .xlsx or CSV .csv)
    """
    from batch.study_config import StudyConfig
    from batch.scheduler import BatchScheduler

    # 加载配置
    if config_path and os.path.exists(config_path):
        config = StudyConfig.from_json(config_path)
        if verbose:
            click.echo(f"Loaded config from: {config_path}")
    else:
        config = StudyConfig(study_name="STUDY")

    # CLI 参数覆盖配置
    if study_name:
        config.study_name = study_name
    if domains:
        config.domains = [d.strip() for d in domains.split(",")]
    config.output_dir = output_dir
    config.rag_enabled = use_rag
    config.rag_mock = rag_mock
    config.lint_enabled = lint
    if kb_path:
        config.kb_path = kb_path
    config.verbose = verbose

    if verbose:
        click.echo(f"Study: {config.study_name}")
        click.echo(f"Domains: {config.domains or 'ALL'}")
        click.echo(f"Output: {config.output_dir}")
        click.echo(f"RAG: {use_rag} (mock={rag_mock})")
        click.echo(f"Lint: {lint}")

    scheduler = BatchScheduler()
    report = scheduler.run(spec_file, config)

    click.echo(f"\nBatch generation complete: {report['successful']}/{report['total_domains']} succeeded")
    click.echo(f"Elapsed: {report['elapsed_seconds']}s")
    click.echo(f"Report: {report['batch_report_path']}")

    if report["failed"] > 0:
        click.echo(f"\nFailed domains:")
        for detail in report["details"]:
            if detail["status"] == "failed":
                click.echo(f"  {detail['domain']}: {detail.get('error', 'Unknown error')}")
        sys.exit(1)


@cli.command()
@click.option("--kb-path", default="D:/Claude code/Knowlegde base", help="Knowledge base path")
@click.option("--force", is_flag=True, help="Force rebuild")
@click.option("--mock", is_flag=True, help="Use mock embedder (testing only)")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def build_kb(kb_path, force, mock, verbose):
    """Build/rebuild the RAG knowledge base."""
    try:
        from rag import create_pipeline
    except ImportError as e:
        click.echo(f"Error: RAG module not available: {e}", err=True)
        sys.exit(1)

    click.echo(f"Building knowledge base from: {kb_path}")

    pipeline = create_pipeline(
        knowledge_base_path=kb_path,
        use_mock_llm=mock
    )

    stats = pipeline.build_knowledge_base(force_rebuild=force)

    click.echo(f"Knowledge base built: {stats}")
    click.echo(f"Storage stats: {pipeline.get_stats()}")


@cli.command()
@click.argument("sas_file", type=click.Path(exists=True))
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def lint(sas_file, output_json):
    """Run L1 linter on a SAS file.

    SAS_FILE: Path to the SAS file to lint
    """
    linter = SASLinter()
    report = linter.lint_file(sas_file)

    if output_json:
        import json
        output = {
            "file": report.file_path,
            "issues": [
                {"line": i.line, "column": i.column, "severity": i.severity, "message": i.message}
                for i in report.issues
            ],
            "stats": report.stats,
            "has_errors": report.has_errors(),
            "has_warnings": report.has_warnings(),
        }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(str(report))

    if report.has_errors():
        sys.exit(1)


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def analyze(spec_file, verbose):
    """Analyze SPEC file and show domain summary.

    SPEC_FILE: Path to the SPEC file (Excel .xlsx or CSV .csv)
    """
    reader = ExcelReader()
    sheets = reader.read(spec_file)
    builder = IRBuilder()

    click.echo(f"SPEC Analysis: {spec_file}")
    click.echo("=" * 50)

    total_vars = 0
    total_template = 0
    total_ai = 0

    for domain, rows in sheets.items():
        domain_ir = builder.build(domain, rows)

        template_vars = sum(1 for v in domain_ir.variables if v.generation == "template")
        ai_vars = sum(1 for v in domain_ir.variables if v.generation == "ai_required")

        total_vars += len(domain_ir.variables)
        total_template += template_vars
        total_ai += ai_vars

        click.echo(f"\n{domain} - {domain_ir.domain_label}")
        click.echo(f"  Variables: {len(domain_ir.variables)}")
        click.echo(f"    Template-generated: {template_vars}")
        click.echo(f"    AI-required: {ai_vars}")

        if verbose:
            click.echo(f"  Variables:")
            for v in domain_ir.variables:
                gen_type = "AI" if v.generation == "ai_required" else "T"
                codelist_str = f" [codelist: {len(v.codelist)} items]" if v.codelist else ""
                click.echo(f"    [{gen_type}] {v.name} ({v.type}, {v.length}){codelist_str}")
                if v.algorithm:
                    click.echo(f"        Algorithm: {v.algorithm[:50]}...")

    click.echo("\n" + "=" * 50)
    click.echo(f"Summary: {len(sheets)} domain(s), {total_vars} variables")
    click.echo(f"  Template: {total_template} ({100*total_template//total_vars if total_vars else 0}%)")
    click.echo(f"  AI-required: {total_ai} ({100*total_ai//total_vars if total_vars else 0}%)")


def _is_variable_sheet(rows: list[dict]) -> bool:
    """检查是否包含 SPEC 变量定义（过滤辅助表）"""
    if not rows:
        return False
    # 检查第一行的 keys 是否包含变量定义的特征列
    first_row = rows[0]
    var_indicators = ['varname', 'variable', 'varlabel', 'label']
    keys_lower = {k.lower() for k in first_row.keys()}
    match_count = sum(1 for ind in var_indicators if any(ind in k for k in keys_lower))
    return match_count >= 2


def main():
    cli()


if __name__ == "__main__":
    main()
