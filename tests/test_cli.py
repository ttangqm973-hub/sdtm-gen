import pytest
import os
import tempfile
from click.testing import CliRunner
from cli import cli


class TestCLI:
    def test_cli_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output

    def test_generate_command(self):
        runner = CliRunner()
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        spec_file = os.path.join(fixtures_dir, "sample_ae_spec.csv")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["generate", spec_file, "-o", tmpdir])
            assert result.exit_code == 0
            assert "Generated" in result.output
            assert os.path.exists(os.path.join(tmpdir, "ae.sas"))

    def test_generate_with_lint(self):
        runner = CliRunner()
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        spec_file = os.path.join(fixtures_dir, "sample_ae_spec.csv")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["generate", spec_file, "-o", tmpdir, "--lint"])
            assert result.exit_code == 0

    def test_generate_verbose(self):
        runner = CliRunner()
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        spec_file = os.path.join(fixtures_dir, "sample_ae_spec.csv")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["generate", spec_file, "-o", tmpdir, "-v"])
            assert result.exit_code == 0
            assert "Processing domain" in result.output

    def test_lint_command(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sas", delete=False, encoding="utf-8") as f:
            f.write("data test; x = 1; run;")
            temp_sas = f.name
        try:
            result = runner.invoke(cli, ["lint", temp_sas])
            assert result.exit_code == 0
            assert "Lint Report" in result.output
        finally:
            os.unlink(temp_sas)

    def test_lint_command_with_errors(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sas", delete=False, encoding="utf-8") as f:
            f.write("data test; x = 1;")
            temp_sas = f.name
        try:
            result = runner.invoke(cli, ["lint", temp_sas])
            assert result.exit_code == 1
        finally:
            os.unlink(temp_sas)

    def test_lint_json_output(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sas", delete=False, encoding="utf-8") as f:
            f.write("data test; x = 1; run;")
            temp_sas = f.name
        try:
            result = runner.invoke(cli, ["lint", temp_sas, "--json"])
            assert result.exit_code == 0
            assert '"file"' in result.output
            assert '"stats"' in result.output
        finally:
            os.unlink(temp_sas)

    def test_analyze_command(self):
        runner = CliRunner()
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        spec_file = os.path.join(fixtures_dir, "sample_ae_spec.csv")
        result = runner.invoke(cli, ["analyze", spec_file])
        assert result.exit_code == 0
        assert "SPEC Analysis" in result.output
        assert "AE" in result.output

    def test_analyze_verbose(self):
        runner = CliRunner()
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        spec_file = os.path.join(fixtures_dir, "sample_ae_spec.csv")
        result = runner.invoke(cli, ["analyze", spec_file, "-v"])
        assert result.exit_code == 0
        assert "STUDYID" in result.output

    def test_generate_nonexistent_file(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "nonexistent.csv"])
        assert result.exit_code != 0

    def test_generate_with_rag_mock(self):
        """验证 --rag --rag-mock 能成功生成含 AI 标记的 SAS 文件"""
        runner = CliRunner()
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        spec_file = os.path.join(fixtures_dir, "sample_ae_spec.csv")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli, ["generate", spec_file, "-o", tmpdir, "--rag", "--rag-mock", "-v"]
            )
            assert result.exit_code == 0, result.output
            assert "RAG pipeline initialized" in result.output
            assert "AI-required" in result.output
            # 检查生成的文件包含 AI 标记
            sas_file = os.path.join(tmpdir, "ae.sas")
            assert os.path.exists(sas_file)
            with open(sas_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert "[AI-GEN-START]" in content
            assert "[AI-GEN-END]" in content

    def test_generate_with_rag_missing_key(self):
        """验证 --rag（无 mock）在缺少 API key 时报错"""
        runner = CliRunner()
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        spec_file = os.path.join(fixtures_dir, "sample_ae_spec.csv")
        # 临时清除 API key
        original_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli, ["generate", spec_file, "-o", tmpdir, "--rag", "-v"]
                )
                # 由于知识库构建和 IR 构建在前，API key 检查在生成阶段触发
                # 应该能看到错误信息或 warning
                assert result.exit_code != 0 or "ANTHROPIC_API_KEY" in result.output or "Error" in result.output
        finally:
            if original_key:
                os.environ["ANTHROPIC_API_KEY"] = original_key

    def test_build_kb_mock(self):
        """验证 build-kb --mock 成功构建知识库"""
        runner = CliRunner()
        result = runner.invoke(cli, ["build-kb", "--mock", "--force"])
        assert result.exit_code == 0, result.output
        assert "built" in result.output.lower() or "Knowledge base" in result.output
