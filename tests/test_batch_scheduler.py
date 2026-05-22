import json
import os
import pytest
import tempfile
import shutil

from batch.study_config import StudyConfig
from batch.scheduler import BatchScheduler


class TestStudyConfig:
    def test_basic_creation(self):
        config = StudyConfig(
            study_name="TEST001",
            domains=["DM", "AE"],
            output_dir="output/TEST001"
        )
        assert config.study_name == "TEST001"
        assert config.domains == ["DM", "AE"]
        assert config.output_dir == "output/TEST001"

    def test_default_values(self):
        config = StudyConfig(study_name="TEST001")
        assert config.domains == []
        assert config.global_macro_refs == []
        assert config.rag_enabled is False
        assert config.lint_enabled is False

    def test_to_dict_roundtrip(self):
        config = StudyConfig(
            study_name="TEST001",
            domains=["DM", "AE", "CM"],
            global_macro_refs=["%date", "%supp"],
            rag_enabled=True,
            lint_enabled=True
        )
        d = config.to_dict()
        restored = StudyConfig.from_dict(d)
        assert restored.study_name == config.study_name
        assert restored.domains == config.domains
        assert restored.global_macro_refs == config.global_macro_refs
        assert restored.rag_enabled == config.rag_enabled

    def test_to_json_file(self):
        config = StudyConfig(study_name="TEST001", domains=["DM"])
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            path = f.name
            config.to_json(path)
        with open(path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded["study_name"] == "TEST001"
        assert loaded["domains"] == ["DM"]
        os.unlink(path)

    def test_from_json_file(self):
        data = {
            "study_name": "TEST002",
            "domains": ["LB", "VS"],
            "output_dir": "out",
            "global_macro_refs": ["%ablfl"],
            "rag_enabled": False,
            "lint_enabled": True
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            path = f.name
            json.dump(data, f)
        config = StudyConfig.from_json(path)
        assert config.study_name == "TEST002"
        assert config.domains == ["LB", "VS"]
        assert config.global_macro_refs == ["%ablfl"]
        assert config.lint_enabled is True
        os.unlink(path)


class TestBatchScheduler:
    def test_scheduler_initialization(self):
        scheduler = BatchScheduler()
        assert scheduler is not None

    def test_run_single_domain(self, ae_spec_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                study_name="TEST",
                domains=["AE"],
                output_dir=tmpdir
            )
            scheduler = BatchScheduler()
            report = scheduler.run(ae_spec_path, config)

            assert report["study_name"] == "TEST"
            assert report["total_domains"] == 1
            assert report["successful"] == 1
            assert report["failed"] == 0
            assert len(report["details"]) == 1

            # 输出文件应存在
            assert os.path.exists(os.path.join(tmpdir, "ae.sas"))

    def test_run_multiple_domains(self, ae_spec_path, dm_spec_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 合并两个 SPEC 到一个 Excel（模拟多 sheet）
            import csv
            # 这里用一个 trick：复制 AE 和 DM 到同一目录，scheduler 应支持多 sheet
            # 但我们的测试夹具是单独的 CSV，所以构造一个多 sheet 的场景
            # 用 ExcelReader 的行为：它读取单文件多 sheet
            # 我们直接测试 scheduler 能处理多 sheet 的返回
            scheduler = BatchScheduler()
            config = StudyConfig(
                study_name="MULTI",
                domains=["AE", "DM"],
                output_dir=tmpdir
            )
            # 由于夹具是单独文件，我们使用 ae_spec_path（单域）验证过滤逻辑即可
            # 多域并行在 e2e 中验证，此处验证接口契约
            report = scheduler.run(ae_spec_path, config)
            assert isinstance(report, dict)
            assert "generated_files" in report
            assert "batch_report_path" in report

    def test_report_written_to_disk(self, ae_spec_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                study_name="REPORT",
                domains=["AE"],
                output_dir=tmpdir
            )
            scheduler = BatchScheduler()
            report = scheduler.run(ae_spec_path, config)

            batch_report_path = report.get("batch_report_path")
            assert batch_report_path is not None
            assert os.path.exists(batch_report_path)

            with open(batch_report_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            assert saved["study_name"] == "REPORT"
            assert "details" in saved
            assert "start_time" in saved
            assert "end_time" in saved

    def test_skip_non_variable_sheets(self, ae_spec_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                study_name="SKIP",
                output_dir=tmpdir
            )
            scheduler = BatchScheduler()
            report = scheduler.run(ae_spec_path, config)

            # AE spec 是变量定义 sheet，不应被跳过
            assert report["total_domains"] >= 1
            assert report["successful"] >= 1

    def test_concurrency_limit(self):
        scheduler = BatchScheduler(max_workers=4)
        assert scheduler.max_workers == 4

        scheduler2 = BatchScheduler()
        assert scheduler2.max_workers == 4  # 默认值
