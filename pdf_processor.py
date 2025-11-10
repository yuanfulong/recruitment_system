"""
PDF处理模块
"""
import pdfplumber
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF处理类"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> Tuple[str, dict]:
        """
        从PDF文件中提取文本
        
        返回：(纯文本, 元数据)
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                page_count = len(pdf.pages)
                
                # 提取每一页的文本
                for i, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += f"\n--- 第{i+1}页 ---\n"
                            text += page_text
                    except Exception as e:
                        logger.warning(f"无法提取第{i+1}页的文本: {str(e)}")
                
                metadata = {
                    "page_count": page_count,
                    "extraction_success": True,
                    "filename": pdf_path.split('/')[-1]
                }
                
                return text.strip(), metadata
        
        except Exception as e:
            logger.error(f"PDF提取失败: {str(e)}")
            raise Exception(f"无法解析PDF文件: {str(e)}")
    
    @staticmethod
    def extract_text_from_bytes(pdf_bytes: bytes) -> Tuple[str, dict]:
        """
        从PDF字节流中提取文本
        """
        import io
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text = ""
                page_count = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += f"\n--- 第{i+1}页 ---\n"
                            text += page_text
                    except Exception as e:
                        logger.warning(f"无法提取第{i+1}页的文本: {str(e)}")
                
                metadata = {
                    "page_count": page_count,
                    "extraction_success": True
                }
                
                return text.strip(), metadata
        
        except Exception as e:
            logger.error(f"PDF提取失败: {str(e)}")
            raise Exception(f"无法解析PDF文件: {str(e)}")


def process_pdf_file(file_path: str) -> Tuple[str, dict]:
    """处理PDF文件"""
    processor = PDFProcessor()
    return processor.extract_text_from_pdf(file_path)


def process_pdf_bytes(pdf_bytes: bytes) -> Tuple[str, dict]:
    """处理PDF字节流"""
    processor = PDFProcessor()
    return processor.extract_text_from_bytes(pdf_bytes)
