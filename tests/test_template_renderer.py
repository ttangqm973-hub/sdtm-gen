import pytest
from generator.template_renderer import TemplateRenderer
from ir.models import Variable, DomainIR


class TestTemplateRenderer:
    def test_render_ae_domain(self):
        variables = [
            Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template"),
            Variable(seq=2, name="USUBJID", label="Unique Subject ID", type="Char", length=20, origin="Predecessor", generation="template"),
            Variable(seq=3, name="AESEQ", label="Sequence Number", type="Num", length=8, origin="Assigned", generation="template"),
        ]
        domain_ir = DomainIR(
            domain="AE",
            domain_label="Adverse Events",
            source_sheet="AE",
            variables=variables,
        )
        renderer = TemplateRenderer()
        code = renderer.render(domain_ir)
        assert "AE" in code
        assert "Adverse Events" in code
        assert "STUDYID" in code

    def test_render_includes_domain_header(self):
        variables = [
            Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template"),
        ]
        domain_ir = DomainIR(domain="AE", domain_label="Adverse Events", source_sheet="AE", variables=variables)
        renderer = TemplateRenderer()
        code = renderer.render(domain_ir)
        # New template uses setpath macro and _setup.sas
        assert "%setpath" in code
        assert "_setup.sas" in code

    def test_render_codelist_variable(self):
        variables = [
            Variable(seq=1, name="AESER", label="Serious Event", type="Char", length=1, origin="CRF", generation="template", codelist={"Y": "Yes", "N": "No"}),
        ]
        domain_ir = DomainIR(domain="AE", domain_label="Adverse Events", source_sheet="AE", variables=variables)
        renderer = TemplateRenderer()
        code = renderer.render(domain_ir)
        # New template uses if-else pattern matching real-world code
        assert "if" in code
        assert "AESER" in code

    def test_render_ai_required_variable(self):
        variables = [
            Variable(seq=1, name="AEREL", label="Causality", type="Char", length=1, origin="Derived", generation="ai_required", algorithm="If AEOUT='FATAL' then AEREL='Y'"),
        ]
        domain_ir = DomainIR(domain="AE", domain_label="Adverse Events", source_sheet="AE", variables=variables)
        renderer = TemplateRenderer()
        code = renderer.render(domain_ir)
        assert "[AI-GEN-START]" in code
        assert "[AI-GEN-END]" in code
        assert "TODO" in code

    def test_render_dm_domain(self):
        variables = [
            Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template"),
            Variable(seq=2, name="USUBJID", label="Unique Subject ID", type="Char", length=20, origin="Predecessor", generation="template"),
        ]
        domain_ir = DomainIR(domain="DM", domain_label="Demographics", source_sheet="DM", variables=variables)
        renderer = TemplateRenderer()
        code = renderer.render(domain_ir, "dm_sdtm.sas.j2")
        assert "DM" in code
        assert "Demographics" in code

    def test_render_includes_date_macro(self):
        variables = [
            Variable(seq=1, name="AESTDTC", label="Start Date", type="Char", length=20, origin="CRF", generation="template"),
        ]
        domain_ir = DomainIR(domain="AE", domain_label="Adverse Events", source_sheet="AE", variables=variables)
        renderer = TemplateRenderer()
        code = renderer.render(domain_ir)
        assert "%date" in code

    def test_render_includes_pre_macro(self):
        variables = [
            Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template"),
        ]
        domain_ir = DomainIR(domain="AE", domain_label="Adverse Events", source_sheet="AE", variables=variables)
        renderer = TemplateRenderer()
        code = renderer.render(domain_ir)
        assert "%pre" in code
