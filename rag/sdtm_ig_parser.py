"""
SDTM IG Parser - SDTM Implementation Guide 解析器

从 SDTM IG PDF 文件中提取规则和指导信息。
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from rag.knowledge_processor import KnowledgeChunk


@dataclass
class IGRule:
    """SDTM IG 规则"""
    id: str
    category: str
    description: str
    domain: Optional[str] = None
    severity: str = "error"
    metadata: dict = field(default_factory=dict)


class SDTMIGParser:
    """SDTM IG PDF 解析器"""

    def __init__(self):
        self.section_patterns = {
            "domain_structure": r"(\d+\.\d+)\s+([A-Z]{2})\s*[-–]\s*(.+)",
            "variable_def": r"(\d+\.\d+\.\d+)\s+([A-Z][A-Z0-9_]*)\s*[-–]\s*(.+)",
            "rule": r"Rule[:：]\s*(.+)",
        }

    def parse_file(self, filepath: str) -> list[KnowledgeChunk]:
        """解析 SDTM IG PDF 文件"""
        try:
            import PyPDF2
        except ImportError:
            print("PyPDF2 not available, skipping SDTM IG parsing")
            return []

        chunks = []

        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)

            # 提取所有文本
            full_text = ""
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    full_text += f"\n--- Page {i+1} ---\n{text}"

        # 解析文档结构
        sections = self._extract_sections(full_text)
        chunks.extend(sections)

        # 提取规则
        rules = self._extract_rules(full_text)
        chunks.extend(rules)

        # 提取域特定信息
        domain_info = self._extract_domain_info(full_text)
        chunks.extend(domain_info)

        # 添加通用知识块
        general_chunks = self._extract_general_knowledge(full_text)
        chunks.extend(general_chunks)

        return chunks

    def _extract_sections(self, text: str) -> list[KnowledgeChunk]:
        """提取章节内容"""
        chunks = []

        # 匹配章节标题
        section_pattern = r"(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z\s]+)\s*\n"
        matches = list(re.finditer(section_pattern, text))

        for i, match in enumerate(matches):
            section_num = match.group(1)
            section_title = match.group(2).strip()

            # 获取章节内容
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            # 限制内容长度
            if len(content) > 2000:
                content = content[:2000] + "..."

            if len(content) > 100:  # 只保留有意义的内容
                chunks.append(KnowledgeChunk(
                    id=f"sdtmig_section_{section_num.replace('.', '_')}",
                    type="sdtm_ig_section",
                    source="SDTMIG_v3.3",
                    domain=None,
                    content=f"Section {section_num}: {section_title}\n\n{content}",
                    metadata={
                        "section_number": section_num,
                        "section_title": section_title
                    }
                ))

        return chunks

    def _extract_rules(self, text: str) -> list[KnowledgeChunk]:
        """提取 SDTM 规则"""
        chunks = []
        rule_id = 0

        # 匹配规则模式
        patterns = [
            # 明确的规则标记
            r"Rule[:：]\s*([^\n]+(?:\n(?![A-Z][a-z]+[:：])[^\n]+)*)",
            # Must/Should/Shall 句式
            r"([A-Z][^.]*\b(must|should|shall|required|mandatory)\b[^.]*\.)",
            # 变量约束
            r"Variable\s+([A-Z][A-Z0-9_]*)\s+must\s+be\s+([^.]+\.)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                rule_text = match.group(0).strip()
                if len(rule_text) > 20 and len(rule_text) < 1000:
                    rule_id += 1

                    # 尝试识别相关域
                    domain_match = re.search(r'\b([A-Z]{2})\b', rule_text)
                    domain = domain_match.group(1) if domain_match else None

                    # 过滤掉非SDTM域
                    valid_domains = {
                        'AE', 'DM', 'CM', 'LB', 'VS', 'EX', 'MH', 'EG',
                        'PE', 'DS', 'SV', 'IE', 'QS', 'RS', 'TR', 'TU',
                        'PR', 'FA', 'CO', 'DD', 'DV', 'SE', 'SS', 'SU',
                        'RELREC', 'TRIAL', 'PC', 'IS', 'PF', 'CV', 'XO',
                        'MI', 'EC', 'TA', 'TE', 'TD', 'TI', 'TS', 'TV'
                    }
                    if domain and domain not in valid_domains:
                        domain = None

                    chunks.append(KnowledgeChunk(
                        id=f"sdtmig_rule_{rule_id}",
                        type="sdtm_rule",
                        source="SDTMIG_v3.3",
                        domain=domain,
                        content=rule_text,
                        metadata={
                            "rule_type": self._classify_rule(rule_text),
                            "severity": self._determine_severity(rule_text)
                        }
                    ))

        return chunks[:200]  # 限制规则数量

    def _extract_domain_info(self, text: str) -> list[KnowledgeChunk]:
        """提取域特定信息"""
        chunks = []

        # SDTM 域列表
        domains = {
            'AE': 'Adverse Events',
            'DM': 'Demographics',
            'CM': 'Concomitant Medications',
            'LB': 'Laboratory Tests Results',
            'VS': 'Vital Signs',
            'EX': 'Exposure',
            'MH': 'Medical History',
            'EG': 'ECG Test Results',
            'PE': 'Physical Examination',
            'DS': 'Disposition',
            'SV': 'Subject Visits',
            'IE': 'Inclusion/Exclusion Criteria Not Met',
            'QS': 'Questionnaires',
            'RS': 'Disease Response',
            'TR': 'Tumor Results',
            'TU': 'Tumor Identification',
            'PR': 'Procedures',
            'FA': 'Findings About',
            'CO': 'Comments',
            'DD': 'Death Details',
            'DV': 'Protocol Deviations',
            'SE': 'Subject Elements',
            'SS': 'Subject Status',
            'SU': 'Substance Use',
            'RELREC': 'Related Records',
            'PC': 'Pharmacokinetics Concentrations',
            'IS': 'Immunogenicity Specimen Assessments',
            'PF': 'Pharmacokinetics Parameter',
            'CV': 'Cardiovascular Findings',
            'XO': 'Exposure as Collected',
            'MI': 'Microscopic Findings',
            'EC': 'Electrocardiogram',
            'TA': 'Trial Arms',
            'TE': 'Trial Elements',
            'TD': 'Trial Disease Assessment',
            'TI': 'Trial Inclusion/Exclusion Criteria',
            'TS': 'Trial Summary',
            'TV': 'Trial Visits'
        }

        for domain_code, domain_name in domains.items():
            # 在文本中查找域相关内容
            pattern = rf"\b{domain_code}\b[^.]*Domain[^.]*\."
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for i, match in enumerate(matches):
                content = match.group(0).strip()
                if len(content) > 30:
                    chunks.append(KnowledgeChunk(
                        id=f"sdtmig_domain_{domain_code}_{i}",
                        type="sdtm_domain",
                        source="SDTMIG_v3.3",
                        domain=domain_code,
                        content=f"{domain_code} - {domain_name}: {content}",
                        metadata={
                            "domain_code": domain_code,
                            "domain_name": domain_name
                        }
                    ))
                    break  # 每个域只取一个

        return chunks

    def _extract_general_knowledge(self, text: str) -> list[KnowledgeChunk]:
        """提取通用 SDTM 知识"""
        chunks = []

        # 关键概念
        concepts = [
            ("Study ID", r"STUDYID[^.]{0,200}"),
            ("Subject ID", r"USUBJID[^.]{0,200}"),
            ("Domain Code", r"DOMAIN[^.]{0,200}"),
            ("Sequence Number", r"--SEQ[^.]{0,200}"),
            ("Reference Start Date", r"RFSTDTC[^.]{0,200}"),
            ("Origin", r"Origin[^.]{0,300}(?:CRF|Derived|Assigned|Predecessor)"),
            ("Variable Label", r"Variable Label[^.]{0,200}"),
            ("Controlled Terms", r"Controlled Terms?[^.]{0,300}"),
        ]

        for concept_name, pattern in concepts:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))[:2]  # 每个概念最多2个
            for i, match in enumerate(matches):
                content = match.group(0).strip()
                if len(content) > 30:
                    chunks.append(KnowledgeChunk(
                        id=f"sdtmig_concept_{concept_name.lower().replace(' ', '_')}_{i}",
                        type="sdtm_concept",
                        source="SDTMIG_v3.3",
                        domain=None,
                        content=f"{concept_name}: {content}",
                        metadata={
                            "concept": concept_name
                        }
                    ))

        return chunks

    def _classify_rule(self, rule_text: str) -> str:
        """分类规则类型"""
        text_lower = rule_text.lower()

        if any(w in text_lower for w in ["must", "mandatory", "required"]):
            return "mandatory"
        elif any(w in text_lower for w in ["should", "recommended"]):
            return "recommended"
        elif any(w in text_lower for w in ["may", "optional", "can"]):
            return "optional"
        else:
            return "general"

    def _determine_severity(self, rule_text: str) -> str:
        """确定规则严重级别"""
        text_lower = rule_text.lower()

        if any(w in text_lower for w in ["must", "mandatory", "required", "shall"]):
            return "error"
        elif any(w in text_lower for w in ["should", "recommended"]):
            return "warning"
        else:
            return "info"


if __name__ == "__main__":
    # 测试
    parser = SDTMIGParser()
    chunks = parser.parse_file("D:/Claude code/Knowlegde base/SDTM IG/SDTMIG_v3.3_FINAL.pdf")
    print(f"Extracted {len(chunks)} chunks from SDTM IG")

    # 显示类型分布
    by_type = {}
    for chunk in chunks:
        t = chunk.type
        by_type[t] = by_type.get(t, 0) + 1
    print(f"By type: {by_type}")
