import os
from generator.template_renderer import TemplateRenderer


class SASGenerator:
    def __init__(self, output_dir: str = None, template_dir: str = None):
        self.output_dir = output_dir or "."
        self.renderer = TemplateRenderer(template_dir)

    def generate(self, domain_ir, output_file: str = None) -> str:
        code = self.renderer.render(domain_ir)
        if output_file is None:
            output_file = os.path.join(self.output_dir, f"{domain_ir.domain.lower()}.sas")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(code)
        return output_file

    def generate_to_string(self, domain_ir) -> str:
        return self.renderer.render(domain_ir)
