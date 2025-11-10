"""
LLM集成模块 - 使用Claude API
"""
import json
import logging
import re
from typing import Dict, Any, Optional, List
from langchain_anthropic import ChatAnthropic
from langchain.schema import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


def safe_parse_json(content: str, default_value=None):
    """
    安全的JSON解析，处理各种LLM返回格式
    """
    if not content or not isinstance(content, str):
        logger.warning(f"无效的内容: {type(content)}")
        return default_value or {}

    try:
        # 第一步：清理内容
        content = content.strip()

        # 移除BOM
        if content.startswith('\ufeff'):
            content = content[1:]

        # 移除markdown代码块标记
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        # 第二步：尝试提取JSON块（如果包含文字说明）
        json_match = re.search(r'\{[\s\S]*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group()

        # 第三步：修复常见的JSON格式错误
        # 移除中文引号，替换为英文
        content = content.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")

        # 修复末尾逗号
        content = re.sub(r',(\s*[}\]])', r'\1', content)

        # 关键修复：在JSON字符串值内的换行符前加反斜杠（但只在字符串内）
        # 这是处理LLM返回的多行JSON的关键
        def escape_newlines_in_strings(text):
            """只在JSON字符串值中转义换行符"""
            result = []
            in_string = False
            escape_next = False

            for i, char in enumerate(text):
                if escape_next:
                    result.append(char)
                    escape_next = False
                elif char == '\\':
                    result.append(char)
                    escape_next = True
                elif char == '"' and (i == 0 or text[i - 1] != '\\'):
                    in_string = not in_string
                    result.append(char)
                elif char == '\n' and in_string:
                    # 在字符串内的换行符转义为\n
                    result.append('\\n')
                elif char == '\r' and in_string:
                    result.append('\\r')
                elif char == '\t' and in_string:
                    result.append('\\t')
                else:
                    result.append(char)

            return ''.join(result)

        content = escape_newlines_in_strings(content)

        # 尝试解析
        result = json.loads(content)
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {str(e)[:100]}")
        # 再试一次：尝试用eval（风险较低因为我们控制了格式）
        try:
            # 最后的尝试：使用json.loads配合encoding修复
            result = json.loads(content, strict=False)
            return result
        except:
            return default_value or {}
    except Exception as e:
        logger.error(f"意外错误: {str(e)}")
        return default_value or {}


class LLMService:
    """LLM服务类"""

    def __init__(self, api_key: str, model: str = "claude-opus-4-1-20250805"):
        """初始化LLM服务"""
        self.client = ChatAnthropic(api_key=api_key, model=model)

    def extract_candidate_info(self, text: str) -> Dict[str, Any]:
        """从简历文本中提取结构化信息 - 重点使用正则表达式"""

        import re
        from datetime import datetime

        # 预处理：修复常见的PDF提取错误
        text_clean = text.replace('⽣⽇', '生日').replace('⽣', '生').replace('⽐', '比')
        text_clean = text_clean.replace('⻰', '龙').replace('⼤', '大').replace('⼯', '工')
        text_clean = text_clean.replace('⼈', '人').replace('⼀', '一').replace('⼆', '二').replace('⼋', '八')

        result = {}

        # 1. 提取姓名 - 从"姓名"后面找
        name_patterns = [
            r'姓\s*名\s*([^\s\n]+)',
            r'姓名[：:]\s*([^\s\n]+)',
            r'名\s*字[：:]\s*([^\s\n]+)',
        ]
        result["name"] = None
        for pattern in name_patterns:
            match = re.search(pattern, text_clean)
            if match:
                result["name"] = match.group(1).strip()
                break

        # 如果还是没找到，从简历前面的几行找
        if not result["name"]:
            # 从"基本信息"后面找
            basic_info_match = re.search(r'基本信息[^\n]*\n([^0-9\n]+)', text_clean)
            if basic_info_match:
                line = basic_info_match.group(1)
                # 提取看起来像名字的内容
                words = re.split(r'\s+', line.strip())
                for word in words:
                    if 2 <= len(word) <= 10 and any(c.isalpha() or '\u4e00' <= c <= '\u9fff' for c in word):
                        result["name"] = word
                        break

        # 2. 提取年龄和生日
        result["age"] = None
        result["birth_date"] = None

        # 查找日期格式 YYYY/MM/DD
        date_patterns = [
            r'(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})',
            r'生日[：:]\s*(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})',
            r'出生(?:日期)?[：:]\s*(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text_clean)
            if match:
                year = match.group(1)
                month = match.group(2).zfill(2)
                day = match.group(3).zfill(2)
                result["birth_date"] = f"{year}/{month}/{day}"
                # 计算年龄
                try:
                    birth = datetime.strptime(result["birth_date"], "%Y/%m/%d")
                    result["age"] = datetime.now().year - birth.year
                except:
                    pass
                break

        # 3. 提取电话 - 多种格式
        result["phone"] = None
        phone_patterns = [
            r'电话[：:]\s*([0-9\-\s]{10,})',
            r'(?:1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}|1[3-9]\d{2}[-\s]?\d{3}[-\s]?\d{4})',
            r'15[0-9]{1}\-?[0-9]{4}\-?[0-9]{4}',  # 特定格式
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, text_clean)
            if match:
                phone = match.group(0) if '电话' not in match.group(0) else match.group(1)
                result["phone"] = phone.replace('-', '').replace(' ', '').strip()
                break

        # 4. 提取邮箱 - 所有邮箱
        result["email"] = None
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+'
        emails = re.findall(email_pattern, text_clean)
        if emails:
            result["email"] = ', '.join(emails)  # 所有邮箱用逗号连接

        # 5. 提取性别
        result["gender"] = None
        if re.search(r'性\s*别[：:]\s*男', text_clean):
            result["gender"] = "男"
        elif re.search(r'性\s*别[：:]\s*女', text_clean):
            result["gender"] = "女"

        # 6. 提取技能
        result["skills"] = []
        # 从"个人能力"或"技能"部分提取
        skills_section = re.search(r'(?:个人能力|技能|技术栈)[：:\s]*([^【]*?)(?=【|个人|获奖|奖学|校园|教育|学术|$)',
                                   text_clean, re.DOTALL)
        if skills_section:
            skills_text = skills_section.group(1)
            # 查找编程语言
            lang_pattern = r'(?:编程语言|语言)[：:]*([^，。\n]*)'
            lang_match = re.search(lang_pattern, skills_text)
            if lang_match:
                langs = re.findall(r'[A-Za-z#\+]+', lang_match.group(1))
                for lang in langs:
                    if lang.upper() in ['C', 'JAVA', 'PYTHON', 'CPP', 'JS', 'GOLANG', 'RUST']:
                        result["skills"].append({
                            "skill": lang,
                            "level": "中级",
                            "years": None
                        })

            # 查找其他技能
            skill_keywords = [
                ('Git', 'git'),
                ('MySQL', 'mysql|数据库'),
                ('机器学习', '机器学习'),
                ('深度学习', '深度学习'),
                ('LLM', 'llm|大语言模型'),
            ]
            for skill_name, pattern in skill_keywords:
                if re.search(pattern, skills_text, re.IGNORECASE):
                    if not any(s["skill"] == skill_name for s in result["skills"]):
                        result["skills"].append({
                            "skill": skill_name,
                            "level": "中级",
                            "years": None
                        })

        # 7. 提取教育背景
        result["education"] = []
        edu_section = re.search(r'教育背景[：:]*([^【]*?)(?=【|个人|校园|工作|获奖|$)', text_clean, re.DOTALL)
        if edu_section:
            edu_text = edu_section.group(1)
            # 查找学校名称
            school_match = re.search(r'([\w\s\(\)（）\u4e00-\u9fff]+?)(?:，|，|大学|学部|学院)', edu_text)
            if school_match:
                result["education"].append({
                    "school": school_match.group(1).strip(),
                    "major": "软件工程" if "软件" in edu_text else "计算机科学",
                    "degree": "本科" if "本科" in edu_text else "其他"
                })

        # 8. 提取自我评价
        result["self_evaluation"] = ""
        eval_section = re.search(r'(?:个人陈述|自我评价|自我介绍)[：:]*([^【\n]*)', text_clean)
        if eval_section:
            result["self_evaluation"] = eval_section.group(1).strip()[:200]

        # 设置默认值
        result.setdefault("name", "求职者")
        result.setdefault("age", 24 if result.get("birth_date") else None)
        result.setdefault("phone", None)
        result.setdefault("email", None)
        result.setdefault("gender", None)
        result.setdefault("work_experience", [])
        result.setdefault("certifications", [])
        result.setdefault("extraction_quality", 75 if result.get("name") != "求职者" else 50)

        logger.info(
            f"✓ 提取候选人: {result.get('name')} | 年龄: {result.get('age')} | 电话: {result.get('phone')} | 邮箱: {result.get('email')} | 质量: {result.get('extraction_quality')}%")
        return result

    def analyze_job_intention(self, candidate_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析候选人的求职意向"""
        prompt = f"""根据以下候选人信息，判断是否有明确的求职意向。

姓名：{candidate_info.get('name', 'N/A')}
自我评价：{candidate_info.get('self_evaluation', 'N/A')}
最新职位：{candidate_info.get('work_experience', [{}])[0].get('position', 'N/A') if candidate_info.get('work_experience') else 'N/A'}

只返回JSON，不要其他文字：

{{
    "has_explicit_position": true或false,
    "explicit_position": "具体职位名称或null",
    "explicit_position_source": "来源信息或null",
    "reasoning": "分析理由"
}}"""

        response = self.client.invoke([HumanMessage(content=prompt)])
        result = safe_parse_json(
            response.content,
            default_value={
                "has_explicit_position": False,
                "explicit_position": None,
                "explicit_position_source": None,
                "reasoning": "无法分析"
            }
        )

        logger.info(f"✓ 求职意向分析完成: {result.get('explicit_position', '无明确意向')}")
        return result

    def evaluate_candidate_for_position(self, candidate_info: Dict[str, Any],
                                        position_name: str,
                                        position_description: str,
                                        required_skills: List[str]) -> Dict[str, Any]:
        """为候选人对某个岗位进行评分"""

        skills_str = ', '.join([s.get('skill', s) if isinstance(s, dict) else s
                                for s in candidate_info.get('skills', [])])

        prompt = f"""为候选人对岗位进行评分。

岗位：{position_name}
描述：{position_description}
核心要求：{', '.join(required_skills)}

候选人技能：{skills_str}

只返回JSON，不要其他文字：

{{
    "overall_score": 60到100的数字,
    "grade": "A或B或C或D",
    "evaluation_reason": "评分理由",
    "matches": ["匹配项1", "匹配项2"],
    "gaps": ["缺陷1", "缺陷2"],
    "potential": "低或中或高"
}}"""

        response = self.client.invoke([HumanMessage(content=prompt)])
        result = safe_parse_json(
            response.content,
            default_value={
                "overall_score": 50,
                "grade": "D",
                "evaluation_reason": "无法评分",
                "matches": [],
                "gaps": [],
                "potential": "低"
            }
        )

        # 确保分数在0-100范围内
        try:
            score = int(result.get('overall_score', 50))
            result['overall_score'] = max(0, min(100, score))
        except (ValueError, TypeError):
            result['overall_score'] = 50

        # 根据分数自动判定等级
        score = result['overall_score']
        if score >= 86:
            result['grade'] = 'A'
        elif score >= 76:
            result['grade'] = 'B'
        elif score >= 60:
            result['grade'] = 'C'
        else:
            result['grade'] = 'D'

        logger.info(f"✓ 岗位评分完成: {position_name} - {result['overall_score']}分({result['grade']}级)")
        return result

    def analyze_position(self, position_name: str, description: str) -> Dict[str, Any]:
        """分析岗位，提炼核心要求和评分指南"""
        prompt = f"""分析岗位需求。

岗位名称：{position_name}
岗位描述：{description}

只返回JSON，不要其他文字：

{{
    "position_name": "{position_name}",
    "base_score": 60,
    "required_skills": ["要求1", "要求2", "要求3"],
    "nice_to_have": ["加分项1", "加分项2"],
    "evaluation_prompt": "60分=满足基本要求, 75分=超出要求, 85分=非常符合, 100分=完全符合"
}}"""

        response = self.client.invoke([HumanMessage(content=prompt)])
        result = safe_parse_json(
            response.content,
            default_value={
                "position_name": position_name,
                "base_score": 60,
                "required_skills": ["相关经验", "基本技能"],
                "nice_to_have": ["加分项"],
                "evaluation_prompt": "基础评分：60分为满足基本要求。75分为超出要求。85分为非常符合。100分为完全符合。"
            }
        )

        # 确保必要字段存在
        result.setdefault('position_name', position_name)
        result.setdefault('base_score', 60)
        result.setdefault('required_skills', ["相关经验"])
        result.setdefault('nice_to_have', ["加分项"])
        result.setdefault('evaluation_prompt', "基础评分：60分为满足基本要求。")

        logger.info(f"✓ 岗位分析完成: {position_name}")
        return result

    def match_position_to_intention(self, new_position_name: str,
                                    explicit_position: str) -> Dict[str, Any]:
        """判断新岗位是否与候选人的求职意向匹配"""
        prompt = f"""判断两个岗位是否匹配。

求职意向：{explicit_position}
系统岗位：{new_position_name}

只返回JSON，不要其他文字：

{{
    "match": true或false,
    "confidence": 0.0到1.0的数字,
    "reasoning": "理由"
}}"""

        response = self.client.invoke([HumanMessage(content=prompt)])
        result = safe_parse_json(
            response.content,
            default_value={
                "match": False,
                "confidence": 0.0,
                "reasoning": "无法判断"
            }
        )

        logger.info(f"✓ 岗位匹配判断: {explicit_position} vs {new_position_name} = {result.get('match')}")
        return result

    def understand_natural_language_query(self, query: str) -> Dict[str, Any]:
        """理解自然语言查询，转换为结构化查询参数"""
        prompt = f"""理解查询意图。

查询："{query}"

只返回JSON，不要其他文字：

{{
    "query_type": "position_candidates或candidate_positions或statistics",
    "filters": {{}},
    "sort_by": null,
    "limit": 20,
    "reasoning": "理由"
}}"""

        response = self.client.invoke([HumanMessage(content=prompt)])
        result = safe_parse_json(
            response.content,
            default_value={
                "query_type": "statistics",
                "filters": {},
                "sort_by": None,
                "limit": 20,
                "reasoning": "默认统计查询"
            }
        )

        logger.info(f"✓ 查询理解完成: {result.get('query_type')}")
        return result

    def generate_query_summary(self, query_results: List[Dict[str, Any]],
                               original_query: str) -> str:
        """生成查询结果的人类可读总结"""

        if not query_results:
            return "查询没有返回任何结果。"

        prompt = f"""生成查询结果总结。

原始查询：{original_query}
结果数量：{len(query_results)}

结果样本：
{json.dumps(query_results[:5], ensure_ascii=False, indent=2)}

用中文生成简明总结（不要返回JSON）。"""

        response = self.client.invoke([HumanMessage(content=prompt)])

        logger.info(f"✓ 查询总结生成完成")
        return response.content


def create_llm_service(api_key: str) -> LLMService:
    """创建LLM服务实例"""
    if not api_key:
        logger.warning("⚠ API_KEY为空，LLM服务可能无法工作")
    return LLMService(api_key=api_key)