import os
import re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape


class TemplateRenderer:
    def __init__(self, template_dir: str = None):
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "sas")
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, domain_ir, template_name: str = None) -> str:
        if template_name is None:
            template_name = f"{domain_ir.domain.lower()}_sdtm.sas.j2"
        template = self.env.get_template(template_name)

        # 构建 AI 生成代码映射
        ai_code_map = {}
        for var in domain_ir.variables:
            if var.ai_generated_code:
                ai_code_map[var.name] = var.ai_generated_code

        result = template.render(
            domain=domain_ir.domain,
            domain_label=domain_ir.domain_label,
            variables=domain_ir.variables,
            macro_refs=domain_ir.macro_refs,
            cross_domain_refs=domain_ir.cross_domain_refs,
            generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ai_summary=domain_ir.ai_summary,
        )

        # 后处理：替换 AI-GEN 标记
        result = self._inject_ai_code(result, ai_code_map, domain_ir)

        return result

    def _inject_ai_code(self, rendered: str, ai_code_map: dict, domain_ir) -> str:
        """将 AI 生成的代码注入渲染后的模板"""

        def replace_ai_block(match):
            block = match.group(0)
            domain_in_block = match.group(1)
            var_name = match.group(2)

            if var_name in ai_code_map:
                code = ai_code_map[var_name]
                domain = domain_ir.domain
                confidence = 0.0
                for v in domain_ir.variables:
                    if v.name == var_name and v.ai_confidence:
                        confidence = v.ai_confidence

                return f"/* [AI-GEN-START] domain={domain} variable={var_name} confidence={confidence:.2f} */\n{code}\n/* [AI-GEN-END] */"
            return block

        # 匹配 [AI-GEN-START] ... [AI-GEN-END] 块
        pattern = r'/\*\s*\[AI-GEN-START\]\s*domain=(\w+)\s+variable=([\w/]+)\s*\*/(.*?)/\*\s*\[AI-GEN-END\]\s*\*/'

        return re.sub(pattern, replace_ai_block, rendered, flags=re.DOTALL)
