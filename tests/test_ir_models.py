import pytest
from ir.models import Variable, DomainIR


class TestVariable:
    def test_basic_variable_creation(self):
        v = Variable(
            seq=1,
            name="STUDYID",
            label="Study Identifier",
            type="Char",
            length=20,
            origin="Assigned",
            generation="template"
        )
        assert v.seq == 1
        assert v.name == "STUDYID"
        assert v.origin == "Assigned"

    def test_variable_with_codelist(self):
        v = Variable(
            seq=2,
            name="AESER",
            label="Serious Event",
            type="Char",
            length=1,
            origin="CRF",
            codelist={"Y": "Yes", "N": "No"},
            generation="template"
        )
        assert v.codelist == {"Y": "Yes", "N": "No"}
        assert v.generation == "template"

    def test_variable_with_algorithm(self):
        v = Variable(
            seq=3,
            name="AEREL",
            label="Causality",
            type="Char",
            length=1,
            origin="Derived",
            generation="ai_required",
            algorithm="若 AEOUT='FATAL' 则 AEREL='Y'",
            ai_context={"related_vars": ["AEOUT"], "related_domains": [], "logic_type": "conditional_derivation"}
        )
        assert v.generation == "ai_required"
        assert v.algorithm is not None

    def test_optional_fields_default_to_none(self):
        v = Variable(
            seq=4,
            name="AESEQ",
            label="Sequence Number",
            type="Num",
            length=8,
            origin="Derived",
            generation="template"
        )
        assert v.codelist is None
        assert v.algorithm is None
        assert v.ai_context is None

    def test_variable_type_enum(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Variable(seq=1, name="X", label="X", type="Other", length=8, origin="CRF", generation="template")


class TestDomainIR:
    def test_basic_domain_creation(self):
        v1 = Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template")
        v2 = Variable(seq=2, name="USUBJID", label="Unique Subject ID", type="Char", length=20, origin="Assigned", generation="template")
        domain = DomainIR(
            domain="AE",
            domain_label="Adverse Events",
            source_sheet="AE",
            variables=[v1, v2],
        )
        assert domain.domain == "AE"
        assert len(domain.variables) == 2
        assert domain.primary_key == []

    def test_domain_with_primary_key_and_macros(self):
        v = Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template")
        domain = DomainIR(
            domain="AE",
            domain_label="Adverse Events",
            source_sheet="AE",
            primary_key=["STUDYID", "USUBJID", "AESEQ"],
            variables=[v],
            macro_refs=["%derive_yn", "%merge_cm"],
            cross_domain_refs=["CM"],
            template_name="ae_standard"
        )
        assert domain.primary_key == ["STUDYID", "USUBJID", "AESEQ"]
        assert "%derive_yn" in domain.macro_refs

    def test_template_variable_ratio(self):
        variables = [
            Variable(seq=i, name=f"V{i}", label=f"V{i}", type="Char", length=8,
                     origin="Assigned" if i % 2 == 0 else "Derived",
                     generation="template" if i % 2 == 0 else "ai_required")
            for i in range(10)
        ]
        domain = DomainIR(domain="XX", domain_label="XX", source_sheet="XX", variables=variables)
        template_vars = [v for v in domain.variables if v.generation == "template"]
        assert len(template_vars) == 5
