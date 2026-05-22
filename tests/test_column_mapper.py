import pytest
from parser.column_mapper import ColumnMapper


class TestColumnMapper:
    def test_map_basic_columns(self):
        mapper = ColumnMapper()
        row = {
            "VARIABLE": "STUDYID",
            "LABEL": "Study Identifier",
            "TYPE": "Char",
            "LENGTH": "20",
            "ORIGIN": "Assigned",
            "CODELIST": "",
            "ALGORITHM": "",
            "CONDITION": "",
            "COMMENT": "",
        }
        result = mapper.map_row(row)
        assert result["variable_name"] == "STUDYID"
        assert result["variable_label"] == "Study Identifier"
        assert result["data_type"] == "Char"
        assert result["origin"] == "Assigned"

    def test_map_codelist(self):
        mapper = ColumnMapper()
        row = {
            "VARIABLE": "AESER",
            "LABEL": "Serious Event",
            "TYPE": "Char",
            "LENGTH": "1",
            "ORIGIN": "CRF",
            "CODELIST": "Y=是;N=否",
            "ALGORITHM": "",
            "CONDITION": "",
            "COMMENT": "",
        }
        result = mapper.map_row(row)
        assert result["codelist_parsed"] == {"Y": "是", "N": "否"}

    def test_map_codelist_single(self):
        mapper = ColumnMapper()
        row = {
            "VARIABLE": "AGEU",
            "LABEL": "Age Units",
            "TYPE": "Char",
            "LENGTH": "5",
            "ORIGIN": "Assigned",
            "CODELIST": "YEARS=岁",
            "ALGORITHM": "",
            "CONDITION": "",
            "COMMENT": "",
        }
        result = mapper.map_row(row)
        assert result["codelist_parsed"] == {"YEARS": "岁"}

    def test_map_empty_codelist_returns_none(self):
        mapper = ColumnMapper()
        row = {
            "VARIABLE": "STUDYID",
            "LABEL": "Study ID",
            "TYPE": "Char",
            "LENGTH": "20",
            "ORIGIN": "Assigned",
            "CODELIST": "",
            "ALGORITHM": "",
            "CONDITION": "",
            "COMMENT": "",
        }
        result = mapper.map_row(row)
        assert result["codelist_parsed"] is None

    def test_map_algorithm_present(self):
        mapper = ColumnMapper()
        row = {
            "VARIABLE": "AEREL",
            "LABEL": "Causality",
            "TYPE": "Char",
            "LENGTH": "1",
            "ORIGIN": "Derived",
            "CODELIST": "",
            "ALGORITHM": "若 AEOUT='FATAL' 则 AEREL='Y'",
            "CONDITION": "",
            "COMMENT": "",
        }
        result = mapper.map_row(row)
        assert result["algorithm_text"] == "若 AEOUT='FATAL' 则 AEREL='Y'"

    def test_detect_columns_new_format(self):
        mapper = ColumnMapper()
        headers = ["VarOrd", "VarName", "VarLabel", "VarType", "VarLen", "Origin", "Algorithm for Programming"]
        mapping = mapper.detect_columns(headers)
        assert "VarName" in mapping
        assert mapping["VarName"] == "variable_name"

    def test_detect_columns_old_format(self):
        mapper = ColumnMapper()
        headers = ["VARIABLE", "LABEL", "TYPE", "LENGTH", "ORIGIN", "CODELIST"]
        mapping = mapper.detect_columns(headers)
        assert "VARIABLE" in mapping
        assert mapping["VARIABLE"] == "variable_name"

    def test_parse_length_special_values(self):
        mapper = ColumnMapper()
        assert mapper._parse_length("~ASDATA") == 8
        assert mapper._parse_length("ASDATA") == 8
        assert mapper._parse_length("200") == 200
        assert mapper._parse_length("") == 8
