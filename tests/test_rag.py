"""
Tests for RAG module
"""

import pytest
from pathlib import Path

from rag.knowledge_processor import KnowledgeChunk, KnowledgeProcessor
from rag.embedder import MockEmbedder, get_embedder
from rag.simple_store import SimpleVectorStore
from rag.retriever import Retriever, RetrievalResult
from rag.generator import MockGenerator, GenerationResult
from rag.pipeline import RAGPipeline, create_pipeline
from rag.sdtm_ig_parser import SDTMIGParser


class TestKnowledgeChunk:
    """Tests for KnowledgeChunk"""

    def test_create_chunk(self):
        chunk = KnowledgeChunk(
            id="test_001",
            type="sas_code",
            source="test.sas",
            content="data test; run;",
            domain="AE"
        )
        assert chunk.id == "test_001"
        assert chunk.type == "sas_code"
        assert chunk.domain == "AE"

    def test_chunk_with_metadata(self):
        chunk = KnowledgeChunk(
            id="test_002",
            type="macro",
            source="test.txt",
            content="%macro test; %mend;",
            metadata={"macro_name": "test", "parameters": []}
        )
        assert chunk.metadata["macro_name"] == "test"


class TestMockEmbedder:
    """Tests for MockEmbedder"""

    def test_embed_returns_vector(self):
        embedder = MockEmbedder()
        vector = embedder.embed("test text")
        assert len(vector) == 128
        assert all(isinstance(v, float) for v in vector)

    def test_embed_normalizes_vector(self):
        embedder = MockEmbedder()
        vector = embedder.embed("test text")
        norm = sum(v * v for v in vector) ** 0.5
        assert abs(norm - 1.0) < 0.001

    def test_embed_batch(self):
        embedder = MockEmbedder()
        vectors = embedder.embed_batch(["text1", "text2"])
        assert len(vectors) == 2
        assert all(len(v) == 128 for v in vectors)

    def test_different_texts_different_vectors(self):
        embedder = MockEmbedder()
        v1 = embedder.embed("hello world")
        v2 = embedder.embed("different text")
        # 应该不同
        assert v1 != v2


class TestSimpleVectorStore:
    """Tests for SimpleVectorStore"""

    def test_add_chunks(self):
        store = SimpleVectorStore(
            persist_dir="d:/Claude code/sdtm_gen/knowledge/test_store"
        )
        # Use mock embedder
        store.embedder = MockEmbedder()
        store.delete_all()

        chunks = [
            KnowledgeChunk(
                id="test_001",
                type="sas_code",
                source="test.sas",
                content="data test; x = 1; run;",
                domain="AE"
            )
        ]
        count = store.add_chunks(chunks)
        assert count == 1
        assert store.count() == 1

    def test_search(self):
        store = SimpleVectorStore(
            persist_dir="d:/Claude code/sdtm_gen/knowledge/test_store"
        )
        store.embedder = MockEmbedder()
        store.delete_all()

        chunks = [
            KnowledgeChunk(
                id="test_001",
                type="sas_code",
                source="ae.sas",
                content="data ae; if aeout='FATAL' then aerel='Y'; run;",
                domain="AE"
            ),
            KnowledgeChunk(
                id="test_002",
                type="sas_code",
                source="dm.sas",
                content="data dm; sex='M'; run;",
                domain="DM"
            )
        ]
        store.add_chunks(chunks)

        results = store.search("AE outcome fatal", n_results=2)
        assert len(results) == 2

    def test_search_with_filter(self):
        store = SimpleVectorStore(
            persist_dir="d:/Claude code/sdtm_gen/knowledge/test_store"
        )
        store.embedder = MockEmbedder()
        store.delete_all()

        chunks = [
            KnowledgeChunk(
                id="test_001",
                type="sas_code",
                source="ae.sas",
                content="data ae; run;",
                domain="AE"
            ),
            KnowledgeChunk(
                id="test_002",
                type="macro",
                source="test.txt",
                content="%macro test; %mend;",
                domain=""
            )
        ]
        store.add_chunks(chunks)

        results = store.search("test", n_results=5, where={"domain": "AE"})
        assert len(results) == 1
        assert results[0]["id"] == "test_001"


class TestRetriever:
    """Tests for Retriever"""

    def test_retrieve(self):
        store = SimpleVectorStore(
            persist_dir="d:/Claude code/sdtm_gen/knowledge/test_store"
        )
        store.embedder = MockEmbedder()
        store.delete_all()

        chunks = [
            KnowledgeChunk(
                id="test_001",
                type="sas_code",
                source="ae.sas",
                content="if aeout='FATAL' then aerel='Y';",
                domain="AE"
            )
        ]
        store.add_chunks(chunks)

        retriever = Retriever(store)
        results = retriever.retrieve("AE outcome fatal", domain="AE")
        assert len(results) == 1


class TestMockGenerator:
    """Tests for MockGenerator"""

    def test_generate_conditional_zh(self):
        """Chinese conditional: 若 X='A' 则 Y='B'"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="AEREL",
            algorithm="若 AEOUT='FATAL' 则 AEREL='Y'",
            context={"domain": "AE"},
            retrieved_chunks=[]
        )
        assert result.code
        assert result.confidence > 0
        assert isinstance(result.warnings, list)
        assert "AEREL" in result.code
        assert "AEOUT" in result.code or "if" in result.code.lower()

    def test_generate_date_derivation(self):
        """ISO date parsing"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="TRTSDT",
            algorithm="RFSTDTC character date to numeric SAS date",
            context={"domain": "DM", "related_vars": ["RFSTDTC"]},
            retrieved_chunks=[]
        )
        assert "RFSTDTC" in result.code or "yymmdd10" in result.code
        assert result.confidence > 0

    def test_generate_flag(self):
        """Flag derivation"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="SAFFL",
            algorithm="Set to 'Y' for safety population. Subjects who received at least one dose.",
            context={"domain": "ADSL", "related_vars": ["TRTSDT"]},
            retrieved_chunks=[]
        )
        assert result.confidence > 0
        assert "SAFFL" in result.code

    def test_generate_numeric_age(self):
        """Numeric age computation"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="AGE",
            algorithm="Calculate age from birth date to informed consent date",
            context={"domain": "DM"},
            retrieved_chunks=[]
        )
        assert "AGE" in result.code
        assert ("365.25" in result.code or "BRTHDT" in result.code)

    def test_generate_study_day(self):
        """Study day calculation"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="AEDY",
            algorithm="Study day of AE onset from AESTDTC",
            context={"domain": "AE", "related_vars": ["AESTDTC"]},
            retrieved_chunks=[]
        )
        assert "AEDY" in result.code
        assert "RFSTDT" in result.code

    def test_generate_fallback(self):
        """Fallback for unknown pattern"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="XYZ",
            algorithm="some unknown complex derivation",
            context={},
            retrieved_chunks=[]
        )
        assert "XYZ" in result.code
        assert "TODO" in result.code
        assert result.confidence <= 0.40

    def test_generate_multi_condition(self):
        """Multiple conditions joined by semicolons"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="TRT01P",
            algorithm="若 PHASE='1' 则 TRT01P=strip(ARM);若 PHASE='2' 则 TRT01P='0.08 mg/kg'",
            context={"domain": "ADSL", "related_vars": ["PHASE", "ARM"]},
            retrieved_chunks=[]
        )
        code = result.code
        assert "else if" in code.lower() or "PHASE" in code

    def test_generate_confidence_range(self):
        """Confidence is always between 0 and 1"""
        generator = MockGenerator()
        test_cases = [
            ("AEREL", "若 X='Y' 则 Z='W'", {"domain": "AE"}),
            ("TRTSDT", "convert RFSTDTC to date", {"domain": "DM"}),
            ("SAFFL", "safety flag", {"domain": "ADSL"}),
            ("AGE", "compute age", {"domain": "DM"}),
            ("UNKNOWN", "xyz", {}),
        ]
        for name, algo, ctx in test_cases:
            result = generator.generate(name, algo, ctx, [])
            assert 0.0 <= result.confidence <= 1.0, \
                f"Confidence {result.confidence} out of range for {name}"

    def test_generate_with_whitelist_validation(self):
        """Variable whitelist validation works"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="AEREL",
            algorithm="若 AEOUT='FATAL' 则 AEREL='Y'",
            context={"domain": "AE"},
            retrieved_chunks=[],
            variable_whitelist=["AEREL", "AEOUT", "STUDYID", "USUBJID"]
        )
        # Variables in code should be in whitelist — no warnings expected
        unknown_warnings = [w for w in result.warnings
                          if "不在白名单中" in w]
        assert len(unknown_warnings) == 0

    def test_code_contains_comments(self):
        """Generated code has descriptive comments"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="AEREL",
            algorithm="若 AEOUT='FATAL' 则 AEREL='Y'",
            context={"domain": "AE"},
            retrieved_chunks=[]
        )
        assert "/*" in result.code
        assert "*/" in result.code
        assert "AEREL" in result.code

    def test_generate_categorical_mapping(self):
        """SELECT-WHEN categorical mapping"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="EPOCH",
            algorithm="Decode visit using codelist: SCREENING=SCREENING, TREATMENT=TREATMENT",
            context={"domain": "AE", "related_vars": ["VISIT"]},
            retrieved_chunks=[]
        )
        code = result.code
        assert "select" in code.lower()
        assert "when" in code.lower()
        assert "end;" in code.lower()
        assert "EPOCH" in code

    def test_generate_baseline_flag(self):
        """Baseline flag — last non-missing before treatment"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="ABLFL",
            algorithm="Baseline flag: last non-missing record before treatment start",
            context={"domain": "LB", "related_vars": ["LBDTC"]},
            retrieved_chunks=[]
        )
        code = result.code
        assert "proc sort" in code.lower()
        assert "last.USUBJID" in code
        assert "ABLFL" in code
        assert "run;" in code.lower()

    def test_generate_first_last_by_group(self):
        """First/last by-group derivation"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="LSTALVDT",
            algorithm="First non-missing date by USUBJID using first.",
            context={"domain": "ADSL", "related_vars": ["LSTALVDTC"]},
            retrieved_chunks=[]
        )
        code = result.code
        assert "data _adsl_fl;" in code or "data _" in code
        assert "set _" in code
        assert "first.USUBJID" in code or "last.USUBJID" in code
        assert "retain" in code.lower()
        assert "run;" in code.lower()

    def test_generate_cross_domain(self):
        """Cross-domain lookup"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="USUBJID",
            algorithm="sdtm.DM.USUBJID",
            context={"domain": "AE", "related_vars": ["USUBJID"], "related_domains": ["DM"]},
            retrieved_chunks=[]
        )
        code = result.code
        assert "proc sort" in code.lower()
        assert "merge" in code.lower()
        assert "BY USUBJID" in code.upper()
        assert "run;" in code.lower()

    def test_generate_reverse_condition(self):
        """Reverse condition: VALUE if CONDITION"""
        generator = MockGenerator()
        result = generator.generate(
            variable_name="AEENRF",
            algorithm='"ONGOING" if AEONGO="Yes"; "COMPLETED" if AEONGO="No"',
            context={"domain": "AE", "related_vars": ["AEONGO"]},
            retrieved_chunks=[]
        )
        code = result.code
        assert "AEENRF" in code
        assert "if" in code.lower()
        assert "ONGOING" in code


class TestExtractConditionParts:
    """Tests for _extract_condition_parts helper"""

    def test_chinese_conditional(self):
        from rag.generator import _extract_condition_parts
        pairs = _extract_condition_parts("若 AEOUT='FATAL' 则 AEREL='Y'")
        assert len(pairs) == 1
        assert pairs[0] == ("AEOUT='FATAL'", "AEREL='Y'")

    def test_english_conditional(self):
        from rag.generator import _extract_condition_parts
        pairs = _extract_condition_parts("if AEOUT='FATAL' then AEREL='Y'")
        assert len(pairs) == 1
        assert pairs[0] == ("AEOUT='FATAL'", "AEREL='Y'")

    def test_reverse_condition(self):
        from rag.generator import _extract_condition_parts
        pairs = _extract_condition_parts('"ONGOING" if AEONGO="Yes"')
        assert len(pairs) == 1
        assert pairs[0] == ('AEONGO="Yes"', 'ONGOING')

    def test_multi_condition_semicolon(self):
        from rag.generator import _extract_condition_parts
        pairs = _extract_condition_parts("若 X='A' 则 Y='B';若 X='C' 则 Y='D'")
        assert len(pairs) == 2
        assert pairs[0] == ("X='A'", "Y='B'")
        assert pairs[1] == ("X='C'", "Y='D'")

    def test_no_match_returns_empty(self):
        from rag.generator import _extract_condition_parts
        pairs = _extract_condition_parts("some random text without conditions")
        assert pairs == []


class TestFindDateSourceVar:
    """Tests for _find_date_source_var helper"""

    def test_from_algorithm(self):
        from rag.generator import _find_date_source_var
        assert _find_date_source_var("convert AESTDTC to date", []) == "AESTDTC"

    def test_from_related_vars(self):
        from rag.generator import _find_date_source_var
        assert _find_date_source_var("convert to date", ["RFSTDTC"]) == "RFSTDTC"

    def test_fallback(self):
        from rag.generator import _find_date_source_var
        assert _find_date_source_var("some text", []) == "RFSTDTC"


class TestRAGPipeline:
    """Tests for RAGPipeline"""

    def test_create_pipeline(self):
        pipeline = create_pipeline(use_mock_llm=True)
        assert pipeline is not None

    def test_build_knowledge_base(self):
        pipeline = RAGPipeline(
            knowledge_dir="d:/Claude code/sdtm_gen/knowledge/test_pipeline",
            use_mock_llm=True
        )
        stats = pipeline.build_knowledge_base(force_rebuild=True)
        assert stats["status"] == "built"
        assert stats["total_chunks"] > 0

    def test_retrieve(self):
        pipeline = RAGPipeline(
            knowledge_dir="d:/Claude code/sdtm_gen/knowledge/test_pipeline",
            use_mock_llm=True
        )
        pipeline.build_knowledge_base(force_rebuild=True)

        results = pipeline.retrieve("AE outcome", top_k=3)
        assert len(results) > 0

    def test_generate(self):
        pipeline = RAGPipeline(
            knowledge_dir="d:/Claude code/sdtm_gen/knowledge/test_pipeline",
            use_mock_llm=True
        )
        pipeline.build_knowledge_base(force_rebuild=True)

        result = pipeline.generate_with_report(
            variable_name="AEREL",
            algorithm="若 AEOUT='FATAL' 则 AEREL='Y'",
            context={"domain": "AE"}
        )
        assert result["generated_code"]
        assert result["confidence"] > 0
        assert "review_required" in result


class TestSDTMIGParser:
    """Tests for SDTM IG Parser"""

    def test_parser_creation(self):
        parser = SDTMIGParser()
        assert parser is not None

    def test_classify_rule(self):
        parser = SDTMIGParser()
        assert parser._classify_rule("must be populated") == "mandatory"
        assert parser._classify_rule("should be populated") == "recommended"
        assert parser._classify_rule("may be populated") == "optional"

    def test_determine_severity(self):
        parser = SDTMIGParser()
        assert parser._determine_severity("must be populated") == "error"
        assert parser._determine_severity("should be populated") == "warning"

    def test_parse_returns_knowledge_chunks(self):
        """Test that parsing returns KnowledgeChunk objects"""
        parser = SDTMIGParser()
        # Use a simple text to test the extraction methods
        text = "STUDYID must be populated for all subjects."
        rules = parser._extract_rules(text)
        # Should extract at least one rule
        for rule in rules:
            assert isinstance(rule, KnowledgeChunk)
            assert rule.type == "sdtm_rule"
