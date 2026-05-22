import pytest
import os
import tempfile
import openpyxl


class TestEndToEnd:
    """End-to-end tests using real SPEC templates from knowledge base."""

    @pytest.fixture
    def knowledge_base_path(self):
        return "D:/Claude code/Knowlegde base"

    def test_read_real_ae_spec(self, knowledge_base_path):
        """Test reading real AE SPEC template."""
        from parser.excel_reader import ExcelReader

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        assert "Variable" in sheets or len(sheets) > 0
        # Check that we got some variables
        for sheet_name, rows in sheets.items():
            if rows:
                assert len(rows) > 0
                break

    def test_build_ir_from_real_spec(self, knowledge_base_path):
        """Test building IR from real SPEC template."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        for sheet_name, rows in sheets.items():
            if rows:
                builder = IRBuilder()
                domain_ir = builder.build("AE", rows)

                assert domain_ir.domain == "AE"
                assert len(domain_ir.variables) > 0

                # Check for standard AE variables
                var_names = [v.name for v in domain_ir.variables]
                assert "STUDYID" in var_names
                assert "USUBJID" in var_names
                break

    def test_generate_sas_from_real_spec(self, knowledge_base_path):
        """Test generating SAS code from real SPEC template."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from generator.sas_generator import SASGenerator

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        for sheet_name, rows in sheets.items():
            if rows:
                builder = IRBuilder()
                domain_ir = builder.build("AE", rows)

                generator = SASGenerator()
                code = generator.generate_to_string(domain_ir)

                # Verify generated code has expected elements
                assert "AE" in code
                assert "%setpath" in code
                assert "%pre" in code
                assert "DOMAIN" in code
                break

    def test_lint_generated_sas(self, knowledge_base_path):
        """Test linting SAS code generated from real SPEC."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from generator.sas_generator import SASGenerator
        from lint.sas_linter import SASLinter

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "DM.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        for sheet_name, rows in sheets.items():
            if rows:
                builder = IRBuilder()
                domain_ir = builder.build("DM", rows)

                generator = SASGenerator()
                code = generator.generate_to_string(domain_ir)

                linter = SASLinter()
                report = linter.lint(code, "dm.sas")

                # Generated code should not have critical errors
                critical_errors = [i for i in report.issues if i.severity == "error" and "Unclosed" in i.message]
                assert len(critical_errors) == 0
                break

    def test_analyze_real_dm_spec(self, knowledge_base_path):
        """Test analyzing real DM SPEC template."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "DM.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        for sheet_name, rows in sheets.items():
            if rows:
                builder = IRBuilder()
                domain_ir = builder.build("DM", rows)

                # Analyze variable generation distribution
                template_count = sum(1 for v in domain_ir.variables if v.generation == "template")
                ai_count = sum(1 for v in domain_ir.variables if v.generation == "ai_required")

                assert template_count > 0
                # Most DM variables should be template-generated
                assert template_count >= ai_count
                break

    def test_full_pipeline_with_real_spec(self, knowledge_base_path):
        """Test full pipeline from SPEC to SAS with real data."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from generator.sas_generator import SASGenerator
        from lint.sas_linter import SASLinter

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        # Step 1: Read SPEC
        reader = ExcelReader()
        sheets = reader.read(spec_path)

        # Step 2: Build IR
        builder = IRBuilder()
        domain_ir = None
        for sheet_name, rows in sheets.items():
            if rows:
                domain_ir = builder.build("AE", rows)
                break

        assert domain_ir is not None

        # Step 3: Generate SAS
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SASGenerator(output_dir=tmpdir)
            output_file = generator.generate(domain_ir)

            assert os.path.exists(output_file)

            # Step 4: Lint
            linter = SASLinter()
            report = linter.lint_file(output_file)

            # Verify no critical structure errors
            assert not any("Unclosed DATA" in i.message for i in report.issues)

    def test_compare_with_real_sas(self, knowledge_base_path):
        """Compare generated SAS with real SAS from knowledge base."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from generator.sas_generator import SASGenerator

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        real_sas_path = os.path.join(knowledge_base_path, "SAS code", "ae.sas")

        if not os.path.exists(spec_path) or not os.path.exists(real_sas_path):
            pytest.skip("Knowledge base files not found")

        # Read real SAS code
        with open(real_sas_path, "r", encoding="utf-8", errors="replace") as f:
            real_sas = f.read()

        # Generate SAS from SPEC
        reader = ExcelReader()
        sheets = reader.read(spec_path)

        builder = IRBuilder()
        domain_ir = None
        for sheet_name, rows in sheets.items():
            if rows:
                domain_ir = builder.build("AE", rows)
                break

        if domain_ir:
            generator = SASGenerator()
            generated_sas = generator.generate_to_string(domain_ir)

            # Compare key elements
            # Both should have domain setup
            assert "DOMAIN" in generated_sas
            assert "DOMAIN" in real_sas

            # Both should have date processing
            assert "%date" in generated_sas or "date" in generated_sas.lower()
            # Real code has date macro

    def test_rag_integration_with_real_spec(self, knowledge_base_path):
        """Test RAG integration with real SPEC template."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from rag.integrator import RAGIntegrator

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        builder = IRBuilder()
        domain_ir = None
        for sheet_name, rows in sheets.items():
            if rows:
                domain_ir = builder.build("AE", rows)
                break

        assert domain_ir is not None

        # Quick check: should have ai_required variables
        ai_vars = [v for v in domain_ir.variables if v.generation == "ai_required"]
        # At least some variables should be AI-required in AE spec
        assert len(ai_vars) > 0

    def test_rag_integration_generation(self, knowledge_base_path):
        """Test RAG integration generates code for ai_required variables."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from rag import create_pipeline
        from rag.integrator import RAGIntegrator

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        builder = IRBuilder()
        domain_ir = None
        for sheet_name, rows in sheets.items():
            if rows:
                domain_ir = builder.build("AE", rows)
                break

        # Process with RAG using mock LLM
        pipeline = create_pipeline(use_mock_llm=True)
        pipeline.build_knowledge_base(force_rebuild=True)

        integrator = RAGIntegrator(pipeline=pipeline)
        domain_ir = integrator.process_domain(domain_ir)

        # Verify ai_required variables got code
        for var in domain_ir.variables:
            if var.generation == "ai_required":
                assert var.ai_generated_code is not None
                assert var.ai_confidence is not None

        # Verify AI summary
        assert domain_ir.ai_summary is not None
        assert domain_ir.ai_summary["total_ai_vars"] > 0
        assert domain_ir.ai_summary["generated"] > 0

    def test_ai_report_export(self, knowledge_base_path):
        """Test AI report export."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from rag import create_pipeline
        from rag.integrator import RAGIntegrator

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        builder = IRBuilder()
        domain_ir = None
        for sheet_name, rows in sheets.items():
            if rows:
                domain_ir = builder.build("AE", rows)
                break

        pipeline = create_pipeline(use_mock_llm=True)
        pipeline.build_knowledge_base(force_rebuild=True)

        integrator = RAGIntegrator(pipeline=pipeline)
        domain_ir = integrator.process_domain(domain_ir)

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = integrator.export_ai_report(domain_ir, tmpdir)
            assert os.path.exists(report_path)

            import json
            with open(report_path, 'r') as f:
                report = json.load(f)
            assert "domain" in report
            assert "ai_summary" in report
            assert "generated_code" in report

    def test_rag_enhanced_sas_generation(self, knowledge_base_path):
        """Test full pipeline: SPEC -> IR -> RAG -> SAS with AI code injection."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from rag import create_pipeline
        from rag.integrator import RAGIntegrator
        from generator.sas_generator import SASGenerator
        from lint.sas_linter import SASLinter

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "AE.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("Knowledge base SPEC template not found")

        # Step 1: Read SPEC
        reader = ExcelReader()
        sheets = reader.read(spec_path)

        builder = IRBuilder()
        domain_ir = None
        for sheet_name, rows in sheets.items():
            if rows:
                domain_ir = builder.build("AE", rows)
                break

        # Step 2: RAG processing
        pipeline = create_pipeline(use_mock_llm=True)
        pipeline.build_knowledge_base(force_rebuild=True)
        integrator = RAGIntegrator(pipeline=pipeline)
        domain_ir = integrator.process_domain(domain_ir)

        # Step 3: Generate SAS with AI code injection
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SASGenerator(output_dir=tmpdir)
            output_file = generator.generate(domain_ir)

            assert os.path.exists(output_file)

            # Read generated file
            with open(output_file, 'r', encoding='utf-8') as f:
                generated_code = f.read()

            # Verify AI-generated code markers are present
            assert "[AI-GEN-START]" in generated_code
            assert "[AI-GEN-END]" in generated_code

            # Step 4: Lint - should still be valid SAS
            linter = SASLinter()
            report = linter.lint_file(output_file)
            assert not any("Unclosed DATA" in i.message for i in report.issues)

    def test_rag_dm_domain_generation(self, knowledge_base_path):
        """Test RAG mock pipeline with DM domain SPEC."""
        from parser.excel_reader import ExcelReader
        from parser.ir_builder import IRBuilder
        from rag import create_pipeline
        from rag.integrator import RAGIntegrator
        from generator.sas_generator import SASGenerator

        spec_path = os.path.join(knowledge_base_path, "SPEC template", "DM.xlsx")
        if not os.path.exists(spec_path):
            pytest.skip("DM SPEC template not found")

        reader = ExcelReader()
        sheets = reader.read(spec_path)

        builder = IRBuilder()
        domain_ir = None
        for sheet_name, rows in sheets.items():
            if rows:
                domain_ir = builder.build("DM", rows)
                break

        assert domain_ir is not None

        pipeline = create_pipeline(use_mock_llm=True)
        pipeline.build_knowledge_base(force_rebuild=True)
        integrator = RAGIntegrator(pipeline=pipeline)
        domain_ir = integrator.process_domain(domain_ir)

        # DM should have some AI-required variables
        ai_vars = [v for v in domain_ir.variables if v.generation == "ai_required"]
        if ai_vars:
            for var in ai_vars:
                assert var.ai_generated_code is not None
                assert var.ai_confidence is not None
                assert 0.0 <= var.ai_confidence <= 1.0

        # Generate SAS
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SASGenerator(output_dir=tmpdir)
            output_file = generator.generate(domain_ir)
            assert os.path.exists(output_file)

    def test_rag_retrieval_relevance(self, knowledge_base_path):
        """Test that retrieval returns results in descending score order."""
        from rag import create_pipeline
        from rag.knowledge_processor import KnowledgeChunk

        pipeline = create_pipeline(use_mock_llm=True)
        # Build with a small set of known chunks for deterministic testing
        pipeline.vector_store.delete_collection("knowledge")
        chunks = [
            KnowledgeChunk(
                id="ae_fatal", type="sas_code", source="ae.sas",
                content="if aeout='FATAL' then aerel='Y';", domain="AE"
            ),
            KnowledgeChunk(
                id="ae_mild", type="sas_code", source="ae.sas",
                content="if aesev='MILD' then aesevn=1;", domain="AE"
            ),
            KnowledgeChunk(
                id="dm_sex", type="sas_code", source="dm.sas",
                content="sex='M';", domain="DM"
            ),
        ]
        pipeline.vector_store.add_chunks(chunks, "knowledge")

        results = pipeline.retrieve("AE fatal outcome", domain="AE", top_k=3)
        assert len(results) > 0
        # Results should be sorted by score descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        # Top result should be AE-related (retrieval semantic test)
        top = results[0]
        assert "ae" in top.id.lower() or "fatal" in top.content.lower()
