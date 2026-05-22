import pytest
import os
import tempfile
from generator.sas_generator import SASGenerator
from ir.models import Variable, DomainIR


class TestSASGenerator:
    def test_generate_to_string(self):
        variables = [
            Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template"),
            Variable(seq=2, name="USUBJID", label="Unique Subject ID", type="Char", length=20, origin="Predecessor", generation="template"),
        ]
        domain_ir = DomainIR(domain="AE", domain_label="Adverse Events", source_sheet="AE", variables=variables)
        generator = SASGenerator()
        code = generator.generate_to_string(domain_ir)
        assert "AE" in code
        assert "STUDYID" in code

    def test_generate_to_file(self):
        variables = [
            Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template"),
        ]
        domain_ir = DomainIR(domain="AE", domain_label="Adverse Events", source_sheet="AE", variables=variables)
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SASGenerator(output_dir=tmpdir)
            output_path = generator.generate(domain_ir)
            assert os.path.exists(output_path)
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "AE" in content

    def test_generate_with_custom_filename(self):
        variables = [
            Variable(seq=1, name="STUDYID", label="Study ID", type="Char", length=20, origin="Assigned", generation="template"),
        ]
        domain_ir = DomainIR(domain="AE", domain_label="Adverse Events", source_sheet="AE", variables=variables)
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "custom_ae.sas")
            generator = SASGenerator()
            output_path = generator.generate(domain_ir, output_file=custom_path)
            assert output_path == custom_path
            assert os.path.exists(custom_path)
