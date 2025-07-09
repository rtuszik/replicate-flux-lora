import os
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict, Optional, Union
from dataclasses import dataclass
from enum import Enum
import json
import base64

from loguru import logger


class OutputType(Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    JSON = "json"
    FILE = "file"
    UNKNOWN = "unknown"


@dataclass
class ProcessedOutput:
    type: OutputType
    data: Any
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Media-specific properties
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    

class OutputHandler:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for different output types
        self.subdirs = {
            OutputType.IMAGE: self.output_dir / "images",
            OutputType.VIDEO: self.output_dir / "videos", 
            OutputType.AUDIO: self.output_dir / "audio",
            OutputType.TEXT: self.output_dir / "text",
            OutputType.JSON: self.output_dir / "json",
            OutputType.FILE: self.output_dir / "files"
        }
        
        for subdir in self.subdirs.values():
            subdir.mkdir(parents=True, exist_ok=True)
        
        # Create thumbnails directory
        self.thumbnails_dir = self.output_dir / "thumbnails"
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    def process_prediction_output(self, output: Any, model_string: str, generation_id: str) -> List[ProcessedOutput]:
        """
        Process the output from a Replicate prediction.
        Returns a list of ProcessedOutput objects.
        """
        processed_outputs = []
        
        if output is None:
            return processed_outputs
        
        # Handle different output formats
        if isinstance(output, list):
            # Multiple outputs (common case)
            for i, item in enumerate(output):
                processed = self._process_single_output(item, model_string, generation_id, i)
                if processed:
                    processed_outputs.append(processed)
        else:
            # Single output
            processed = self._process_single_output(output, model_string, generation_id, 0)
            if processed:
                processed_outputs.append(processed)
        
        return processed_outputs

    def _process_single_output(self, output: Any, model_string: str, generation_id: str, index: int) -> Optional[ProcessedOutput]:
        """Process a single output item"""
        
        # Handle FileOutput objects (replicate-python 1.0+)
        if hasattr(output, 'read') and hasattr(output, 'url'):
            return self._process_file_output(output, model_string, generation_id, index)
        
        # Handle URL strings (legacy format)
        elif isinstance(output, str):
            if output.startswith(('http://', 'https://')):
                return self._process_url_output(output, model_string, generation_id, index)
            elif output.startswith('data:'):
                return self._process_data_url_output(output, model_string, generation_id, index)
            else:
                return self._process_text_output(output, model_string, generation_id, index)
        
        # Handle dictionaries/JSON
        elif isinstance(output, dict):
            return self._process_json_output(output, model_string, generation_id, index)
        
        # Handle primitive types as text
        else:
            return self._process_text_output(str(output), model_string, generation_id, index)

    def _process_file_output(self, file_output, model_string: str, generation_id: str, index: int) -> Optional[ProcessedOutput]:
        """Process a FileOutput object from replicate-python 1.0+"""
        try:
            # Determine file type from URL or content
            url = file_output.url if hasattr(file_output, 'url') else None
            mime_type = self._guess_mime_type_from_url(url) if url else None
            output_type = self._determine_output_type(mime_type)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = self._get_extension_from_mime_type(mime_type) or "bin"
            filename = f"{timestamp}_{generation_id}_{index:03d}.{extension}"
            
            # Save to appropriate directory
            file_path = self.subdirs[output_type] / filename
            
            # Read and save the file
            with open(file_path, 'wb') as f:
                f.write(file_output.read())
            
            file_size = file_path.stat().st_size
            
            # Get media metadata if applicable
            metadata = self._extract_media_metadata(file_path, output_type)
            
            logger.info(f"Saved {output_type.value} output to {file_path}")
            
            return ProcessedOutput(
                type=output_type,
                data=file_output,
                file_path=str(file_path),
                mime_type=mime_type,
                file_size=file_size,
                metadata=metadata,
                width=metadata.get('width') if metadata else None,
                height=metadata.get('height') if metadata else None,
                duration=metadata.get('duration') if metadata else None
            )
            
        except Exception as e:
            logger.error(f"Error processing file output: {e}")
            return None

    def _process_url_output(self, url: str, model_string: str, generation_id: str, index: int) -> Optional[ProcessedOutput]:
        """Process a URL output (legacy format)"""
        try:
            import httpx
            
            # Download the file
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()
            
            # Determine file type
            mime_type = response.headers.get('content-type', '')
            output_type = self._determine_output_type(mime_type)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = self._get_extension_from_mime_type(mime_type) or "bin"
            filename = f"{timestamp}_{generation_id}_{index:03d}.{extension}"
            
            # Save to appropriate directory
            file_path = self.subdirs[output_type] / filename
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            metadata = self._extract_media_metadata(file_path, output_type)
            
            logger.info(f"Downloaded and saved {output_type.value} from {url} to {file_path}")
            
            return ProcessedOutput(
                type=output_type,
                data=url,
                file_path=str(file_path),
                mime_type=mime_type,
                file_size=file_size,
                metadata=metadata,
                width=metadata.get('width') if metadata else None,
                height=metadata.get('height') if metadata else None,
                duration=metadata.get('duration') if metadata else None
            )
            
        except Exception as e:
            logger.error(f"Error processing URL output {url}: {e}")
            return None

    def _process_data_url_output(self, data_url: str, model_string: str, generation_id: str, index: int) -> Optional[ProcessedOutput]:
        """Process a data URL output"""
        try:
            # Parse data URL
            if not data_url.startswith('data:'):
                return None
            
            header, data = data_url.split(',', 1)
            mime_type = header.split(';')[0].split(':')[1]
            
            # Decode base64 data
            if 'base64' in header:
                file_data = base64.b64decode(data)
            else:
                file_data = data.encode('utf-8')
            
            output_type = self._determine_output_type(mime_type)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = self._get_extension_from_mime_type(mime_type) or "bin"
            filename = f"{timestamp}_{generation_id}_{index:03d}.{extension}"
            
            # Save to appropriate directory
            file_path = self.subdirs[output_type] / filename
            
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            file_size = len(file_data)
            metadata = self._extract_media_metadata(file_path, output_type)
            
            logger.info(f"Saved data URL {output_type.value} to {file_path}")
            
            return ProcessedOutput(
                type=output_type,
                data=data_url,
                file_path=str(file_path),
                mime_type=mime_type,
                file_size=file_size,
                metadata=metadata,
                width=metadata.get('width') if metadata else None,
                height=metadata.get('height') if metadata else None,
                duration=metadata.get('duration') if metadata else None
            )
            
        except Exception as e:
            logger.error(f"Error processing data URL output: {e}")
            return None

    def _process_text_output(self, text: str, model_string: str, generation_id: str, index: int) -> ProcessedOutput:
        """Process text output"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{generation_id}_{index:03d}.txt"
        file_path = self.subdirs[OutputType.TEXT] / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        file_size = len(text.encode('utf-8'))
        
        logger.info(f"Saved text output to {file_path}")
        
        return ProcessedOutput(
            type=OutputType.TEXT,
            data=text,
            file_path=str(file_path),
            mime_type="text/plain",
            file_size=file_size
        )

    def _process_json_output(self, json_data: Dict[str, Any], model_string: str, generation_id: str, index: int) -> ProcessedOutput:
        """Process JSON output"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{generation_id}_{index:03d}.json"
        file_path = self.subdirs[OutputType.JSON] / filename
        
        json_str = json.dumps(json_data, indent=2)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        
        file_size = len(json_str.encode('utf-8'))
        
        logger.info(f"Saved JSON output to {file_path}")
        
        return ProcessedOutput(
            type=OutputType.JSON,
            data=json_data,
            file_path=str(file_path),
            mime_type="application/json",
            file_size=file_size
        )

    def _determine_output_type(self, mime_type: str) -> OutputType:
        """Determine OutputType from MIME type"""
        if not mime_type:
            return OutputType.UNKNOWN
        
        mime_type = mime_type.lower()
        
        if mime_type.startswith('image/'):
            return OutputType.IMAGE
        elif mime_type.startswith('video/'):
            return OutputType.VIDEO
        elif mime_type.startswith('audio/'):
            return OutputType.AUDIO
        elif mime_type.startswith('text/'):
            return OutputType.TEXT
        elif mime_type == 'application/json':
            return OutputType.JSON
        else:
            return OutputType.FILE

    def _guess_mime_type_from_url(self, url: str) -> Optional[str]:
        """Guess MIME type from URL"""
        if not url:
            return None
        
        mime_type, _ = mimetypes.guess_type(url)
        return mime_type

    def _get_extension_from_mime_type(self, mime_type: str) -> Optional[str]:
        """Get file extension from MIME type"""
        if not mime_type:
            return None
        
        extension = mimetypes.guess_extension(mime_type)
        if extension:
            return extension.lstrip('.')
        
        # Common mappings not in mimetypes
        common_mappings = {
            'image/webp': 'webp',
            'video/mp4': 'mp4',
            'audio/mpeg': 'mp3',
            'audio/wav': 'wav',
            'application/json': 'json'
        }
        
        return common_mappings.get(mime_type.lower())

    def _extract_media_metadata(self, file_path: Path, output_type: OutputType) -> Optional[Dict[str, Any]]:
        """Extract metadata from media files"""
        metadata = {}
        
        try:
            if output_type == OutputType.IMAGE:
                # Try to get image dimensions
                try:
                    from PIL import Image
                    with Image.open(file_path) as img:
                        metadata['width'] = img.width
                        metadata['height'] = img.height
                        metadata['format'] = img.format
                except ImportError:
                    logger.debug("PIL not available for image metadata extraction")
                except Exception as e:
                    logger.debug(f"Could not extract image metadata: {e}")
            
            elif output_type == OutputType.VIDEO:
                # For video metadata, you'd typically use ffprobe or similar
                # This is a placeholder - implement based on your needs
                metadata['format'] = 'video'
            
            elif output_type == OutputType.AUDIO:
                # For audio metadata, you'd typically use libraries like mutagen
                # This is a placeholder - implement based on your needs
                metadata['format'] = 'audio'
        
        except Exception as e:
            logger.debug(f"Error extracting metadata from {file_path}: {e}")
        
        return metadata if metadata else None

    def generate_thumbnail(self, processed_output: ProcessedOutput) -> Optional[str]:
        """Generate thumbnail for an output"""
        if not processed_output.file_path:
            return None
        
        try:
            thumbnail_filename = f"thumb_{Path(processed_output.file_path).stem}.jpg"
            thumbnail_path = self.thumbnails_dir / thumbnail_filename
            
            if processed_output.type == OutputType.IMAGE:
                return self._generate_image_thumbnail(processed_output.file_path, thumbnail_path)
            elif processed_output.type == OutputType.VIDEO:
                return self._generate_video_thumbnail(processed_output.file_path, thumbnail_path)
            elif processed_output.type == OutputType.TEXT:
                return self._generate_text_thumbnail(processed_output.data, thumbnail_path)
            elif processed_output.type == OutputType.JSON:
                return self._generate_json_thumbnail(processed_output.data, thumbnail_path)
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
        
        return None

    def _generate_image_thumbnail(self, image_path: str, thumbnail_path: Path) -> Optional[str]:
        """Generate thumbnail for image"""
        try:
            from PIL import Image
            
            with Image.open(image_path) as img:
                # Convert RGBA to RGB for JPEG compatibility
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
                
                img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                img.save(thumbnail_path, "JPEG", quality=85)
            
            return str(thumbnail_path)
            
        except ImportError:
            logger.debug("PIL not available for thumbnail generation")
        except Exception as e:
            logger.error(f"Error generating image thumbnail: {e}")
        
        return None

    def _generate_video_thumbnail(self, video_path: str, thumbnail_path: Path) -> Optional[str]:
        """Generate thumbnail for video (placeholder)"""
        # This would typically use ffmpeg or similar
        # For now, return None - implement based on your needs
        return None

    def _generate_text_thumbnail(self, text: str, thumbnail_path: Path) -> Optional[str]:
        """Generate thumbnail for text"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create image with text preview
            img = Image.new('RGB', (200, 200), color='white')
            draw = ImageDraw.Draw(img)
            
            # Try to use a system font, fallback to default
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except:
                font = ImageFont.load_default()
            
            # Wrap text
            wrapped_text = self._wrap_text(text[:200], 25)
            draw.text((10, 10), wrapped_text, fill='black', font=font)
            
            img.save(thumbnail_path, "JPEG", quality=85)
            return str(thumbnail_path)
            
        except ImportError:
            logger.debug("PIL not available for text thumbnail generation")
        except Exception as e:
            logger.error(f"Error generating text thumbnail: {e}")
        
        return None

    def _generate_json_thumbnail(self, json_data: Dict[str, Any], thumbnail_path: Path) -> Optional[str]:
        """Generate thumbnail for JSON data"""
        # Convert JSON to formatted text and create thumbnail
        text = json.dumps(json_data, indent=2)[:200]
        return self._generate_text_thumbnail(text, thumbnail_path)

    def _wrap_text(self, text: str, width: int) -> str:
        """Wrap text to specified width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            if len(' '.join(current_line + [word])) <= width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines[:10])  # Limit to 10 lines

    def cleanup_orphaned_files(self):
        """Remove files that are no longer referenced"""
        # This would be implemented in conjunction with the gallery database
        # to remove files that are not referenced in the database
        pass