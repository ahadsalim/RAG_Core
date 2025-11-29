"""
File Processing Service
Handles OCR for images and text extraction from PDF/TXT files
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import io
import tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
import pytesseract
import structlog

from app.config.settings import settings

logger = structlog.get_logger()


class FileProcessingService:
    """Service for processing uploaded files (images, PDFs, text files)."""
    
    def __init__(self):
        """Initialize file processing service."""
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.supported_image_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        self.supported_text_formats = {'.txt', '.pdf'}
        self.max_file_size_mb = settings.max_image_size_mb
        
        # Configure Tesseract
        if hasattr(settings, 'tesseract_cmd'):
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    
    async def process_file(
        self,
        file_content: bytes,
        filename: str,
        file_type: str
    ) -> Dict[str, Any]:
        """
        Process a single file and extract text content.
        
        Args:
            file_content: Binary content of the file
            filename: Original filename
            file_type: MIME type of the file
            
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # Validate file size
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                raise ValueError(f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed ({self.max_file_size_mb}MB)")
            
            # Determine file extension
            file_ext = Path(filename).suffix.lower()
            
            # Process based on file type
            if file_ext in self.supported_image_formats or file_type.startswith('image/'):
                result = await self._process_image(file_content, filename)
            elif file_ext == '.pdf' or file_type == 'application/pdf':
                result = await self._process_pdf(file_content, filename)
            elif file_ext == '.txt' or file_type == 'text/plain':
                result = await self._process_text(file_content, filename)
            else:
                raise ValueError(f"Unsupported file type: {file_ext} ({file_type})")
            
            logger.info(
                "File processed successfully",
                filename=filename,
                file_type=file_type,
                text_length=len(result.get('text', ''))
            )
            
            return result
            
        except Exception as e:
            logger.error(f"File processing failed: {e}", filename=filename, file_type=file_type)
            raise
    
    async def _process_image(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract text from image using OCR.
        
        Args:
            file_content: Image binary content
            filename: Original filename
            
        Returns:
            Dictionary with extracted text and metadata
        """
        def _ocr_sync():
            """Synchronous OCR processing."""
            # Open image
            image = Image.open(io.BytesIO(file_content))
            
            # Convert to RGB if necessary
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            
            # Perform OCR with Persian and English
            ocr_config = f'--oem 3 --psm 6 -l {settings.ocr_language}'
            text = pytesseract.image_to_string(image, config=ocr_config)
            
            # Get additional metadata
            width, height = image.size
            
            return {
                'text': text.strip(),
                'filename': filename,
                'file_type': 'image',
                'metadata': {
                    'width': width,
                    'height': height,
                    'format': image.format,
                    'mode': image.mode
                }
            }
        
        # Run OCR in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, _ocr_sync)
        return result
    
    async def _process_pdf(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract text from PDF file.
        
        Args:
            file_content: PDF binary content
            filename: Original filename
            
        Returns:
            Dictionary with extracted text and metadata
        """
        def _extract_pdf_sync():
            """Synchronous PDF text extraction."""
            try:
                import PyPDF2
                
                # Create PDF reader
                pdf_file = io.BytesIO(file_content)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                
                # Extract text from all pages
                text_parts = []
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                text = '\n\n'.join(text_parts)
                
                return {
                    'text': text.strip(),
                    'filename': filename,
                    'file_type': 'pdf',
                    'metadata': {
                        'num_pages': len(pdf_reader.pages),
                        'has_encryption': pdf_reader.is_encrypted
                    }
                }
                
            except ImportError:
                # Fallback: If PyPDF2 not available, try pdfplumber
                try:
                    import pdfplumber
                    
                    text_parts = []
                    with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(page_text)
                    
                    text = '\n\n'.join(text_parts)
                    
                    return {
                        'text': text.strip(),
                        'filename': filename,
                        'file_type': 'pdf',
                        'metadata': {
                            'num_pages': len(pdf.pages)
                        }
                    }
                except ImportError:
                    raise RuntimeError("No PDF processing library available. Install PyPDF2 or pdfplumber.")
        
        # Run PDF extraction in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, _extract_pdf_sync)
        return result
    
    async def _process_text(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract text from plain text file.
        
        Args:
            file_content: Text file binary content
            filename: Original filename
            
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # Try UTF-8 first
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback to other encodings
            for encoding in ['utf-8-sig', 'windows-1256', 'iso-8859-1', 'cp1252']:
                try:
                    text = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Unable to decode text file with supported encodings")
        
        return {
            'text': text.strip(),
            'filename': filename,
            'file_type': 'text',
            'metadata': {
                'size_bytes': len(file_content),
                'line_count': len(text.splitlines())
            }
        }
    
    async def process_multiple_files(
        self,
        files: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process multiple files concurrently.
        
        Args:
            files: List of file dictionaries with 'content', 'filename', 'file_type'
            
        Returns:
            List of processing results
        """
        if len(files) > 5:
            raise ValueError("Maximum 5 files allowed per request")
        
        # Process files concurrently
        tasks = [
            self.process_file(
                file_content=file['content'],
                filename=file['filename'],
                file_type=file['file_type']
            )
            for file in files
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process file {files[i]['filename']}: {result}")
                processed_results.append({
                    'filename': files[i]['filename'],
                    'error': str(result),
                    'text': ''
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    def combine_extracted_texts(self, results: List[Dict[str, Any]]) -> str:
        """
        Combine extracted texts from multiple files.
        
        Args:
            results: List of processing results
            
        Returns:
            Combined text with file separators
        """
        combined_parts = []
        
        for result in results:
            if result.get('text'):
                filename = result.get('filename', 'unknown')
                text = result['text']
                combined_parts.append(f"[فایل: {filename}]\n{text}\n")
        
        return '\n---\n'.join(combined_parts)


# Global service instance
_file_processing_service: Optional[FileProcessingService] = None


def get_file_processing_service() -> FileProcessingService:
    """Get or create file processing service instance."""
    global _file_processing_service
    if _file_processing_service is None:
        _file_processing_service = FileProcessingService()
    return _file_processing_service
