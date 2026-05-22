import pytest
from parser.ir_builder import IRBuilder


class TestIRBuilder:
    def test_build_from_rows(self, ae_raw_rows):
        builder = IRBuilder()
        domain_ir = builder.build("AE", ae_raw_rows)
        assert domain_ir.domain == "AE"
        assert len(domain_ir.variables) == 8

    def test_variables_have_correct_types(self, ae_raw_rows):
        builder = IRBuilder()
        domain_ir = builder.build("AE", ae_raw_rows)
        studyid = next(v for v in domain_ir.variables if v.name == "STUDYID")
        assert studyid.origin == "Assigned"
        assert studyid.generation == "template"

    def test_codelist_variable(self, ae_raw_rows):
        builder = IRBuilder()
        domain_ir = builder.build("AE", ae_raw_rows)
        aesser = next(v for v in domain_ir.variables if v.name == "AESER")
        assert aesser.codelist == {"Y": "是", "N": "否"}
        assert aesser.origin == "CRF"

    def test_derived_variable_with_algorithm(self, ae_raw_rows):
        builder = IRBuilder()
        domain_ir = builder.build("AE", ae_raw_rows)
        aerel = next(v for v in domain_ir.variables if v.name == "AEREL")
        assert aerel.origin == "Derived"
        assert aerel.generation == "ai_required"
        assert "FATAL" in aerel.algorithm

    def test_derived_variable_without_algorithm_is_template(self, ae_raw_rows):
        builder = IRBuilder()
        domain_ir = builder.build("AE", ae_raw_rows)
        aeseq = next(v for v in domain_ir.variables if v.name == "AESEQ")
        assert aeseq.origin == "Assigned"
        assert aeseq.generation == "template"

    def test_length_parsed_as_int(self, ae_raw_rows):
        builder = IRBuilder()
        domain_ir = builder.build("AE", ae_raw_rows)
        aeseq = next(v for v in domain_ir.variables if v.name == "AESEQ")
        assert isinstance(aeseq.length, int)
        assert aeseq.length == 8

    def test_dm_domain_correct_count(self, dm_spec_path):
        from parser.excel_reader import ExcelReader
        reader = ExcelReader()
        sheets = reader.read(dm_spec_path)
        rows = sheets["DM"]
        builder = IRBuilder()
        domain_ir = builder.build("DM", rows)
        assert len(domain_ir.variables) == 15
