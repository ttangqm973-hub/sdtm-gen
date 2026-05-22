import pytest
from parser.excel_reader import ExcelReader


class TestExcelReader:
    def test_read_csv_spec(self, ae_spec_path):
        reader = ExcelReader()
        sheets = reader.read(ae_spec_path)
        assert "AE" in sheets
        assert len(sheets["AE"]) == 8

    def test_detect_domain_from_filename(self, ae_spec_path):
        reader = ExcelReader()
        sheets = reader.read(ae_spec_path)
        domain_name = reader.detect_domain(sheets)
        assert domain_name == "AE"

    def test_read_dm_spec(self, dm_spec_path):
        reader = ExcelReader()
        sheets = reader.read(dm_spec_path)
        assert len(sheets["DM"]) == 15

    def test_row_has_all_columns(self, ae_spec_path):
        reader = ExcelReader()
        sheets = reader.read(ae_spec_path)
        first_row = sheets["AE"][0]
        assert "VARIABLE" in first_row
        assert "ORIGIN" in first_row
        assert "CODELIST" in first_row
