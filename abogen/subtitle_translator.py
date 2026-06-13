"""LLM-based subtitle translator for generating bilingual subtitles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib import error, parse, request

from abogen.llm_client import LLMClientError


@dataclass(frozen=True)
class TranslationConfig:
    """Configuration for subtitle translation."""
    base_url: str
    api_key: str
    model: str
    source_language: str = "en"
    target_language: str = "zh"
    timeout: float = 60.0
    batch_size: int = 10

    def is_configured(self) -> bool:
        return bool(self.base_url.strip() and self.model.strip())


@dataclass
class SubtitleEntry:
    """A single subtitle entry with timing and text."""
    index: int
    start_time: str
    end_time: str
    original_text: str
    translated_text: Optional[str] = None


# Language code to full name mapping
LANGUAGE_NAMES = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
}

# Translation prompt template
TRANSLATION_PROMPT = """You are a professional subtitle translator. Translate the following subtitle text from {source_lang} to {target_lang}.

Requirements:
1. Maintain the original meaning and tone
2. Keep translations concise and natural for subtitles
3. Preserve any proper nouns, brand names, or technical terms
4. For music or sound effects in brackets like [Music] or [Applause], keep them as-is
5. Return ONLY the translated text, nothing else

Subtitle text to translate:
{text}"""

BATCH_TRANSLATION_PROMPT = """You are a professional subtitle translator. Translate the following subtitle texts from {source_lang} to {target_lang}.

Requirements:
1. Maintain the original meaning and tone
2. Keep translations concise and natural for subtitles
3. Preserve any proper nouns, brand names, or technical terms
4. For music or sound effects in brackets like [Music] or [Applause], keep them as-is
5. Return a JSON array of translated texts in the same order

Input texts (JSON array):
{texts}

Return ONLY a JSON array of translated texts, nothing else."""


def _normalized_base_url(base_url: str) -> str:
    trimmed = (base_url or "").strip()
    if not trimmed:
        raise LLMClientError("Translation base URL is required")
    if not trimmed.endswith("/"):
        trimmed += "/"
    return trimmed


def _build_url(base_url: str, path: str) -> str:
    normalized = _normalized_base_url(base_url)
    trimmed_path = path.lstrip("/")
    parsed = parse.urlparse(normalized)
    if parsed.path.rstrip("/").lower().endswith("/v1") and trimmed_path.startswith("v1/"):
        trimmed_path = trimmed_path[len("v1/"):]
    return parse.urljoin(normalized, trimmed_path)


def _build_headers(api_key: str) -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = (api_key or "").strip()
    if token and token.lower() != "ollama":
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _perform_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 60.0,
) -> Any:
    data_bytes: Optional[bytes] = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
    request_headers = dict(headers or {})
    req = request.Request(url, data=data_bytes, headers=request_headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read()
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", "ignore") if exc.fp else exc.reason
        raise LLMClientError(f"Translation request failed ({exc.code}): {message}") from exc
    except error.URLError as exc:
        raise LLMClientError(f"Translation request failed: {exc.reason}") from exc
    except Exception as exc:
        raise LLMClientError("Translation request failed") from exc

    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise LLMClientError("Translation response was not valid JSON") from exc


def translate_single_text(
    config: TranslationConfig,
    text: str,
) -> str:
    """Translate a single text using the LLM."""
    if not config.is_configured():
        raise LLMClientError("Translation configuration is incomplete")
    
    if not text.strip():
        return ""

    source_lang = LANGUAGE_NAMES.get(config.source_language, config.source_language)
    target_lang = LANGUAGE_NAMES.get(config.target_language, config.target_language)

    url = _build_url(config.base_url, "v1/chat/completions")
    headers = _build_headers(config.api_key)
    
    prompt = TRANSLATION_PROMPT.format(
        source_lang=source_lang,
        target_lang=target_lang,
        text=text,
    )
    
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "You are a professional subtitle translator."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    response = _perform_request("POST", url, headers=headers, payload=payload, timeout=config.timeout)
    
    if not isinstance(response, dict):
        raise LLMClientError("Unexpected response from translation API")
    
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMClientError("Translation response did not include choices")
    
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise LLMClientError("Translation response message was invalid")
    
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LLMClientError("Translation response did not include text content")
    
    return content.strip()


def translate_batch_texts(
    config: TranslationConfig,
    texts: List[str],
) -> List[str]:
    """Translate multiple texts in a single LLM call for efficiency."""
    if not config.is_configured():
        raise LLMClientError("Translation configuration is incomplete")
    
    if not texts:
        return []
    
    # Filter out empty texts but keep track of positions
    non_empty_indices = []
    non_empty_texts = []
    for i, text in enumerate(texts):
        if text.strip():
            non_empty_indices.append(i)
            non_empty_texts.append(text)
    
    if not non_empty_texts:
        return [""] * len(texts)

    source_lang = LANGUAGE_NAMES.get(config.source_language, config.source_language)
    target_lang = LANGUAGE_NAMES.get(config.target_language, config.target_language)

    url = _build_url(config.base_url, "v1/chat/completions")
    headers = _build_headers(config.api_key)
    
    prompt = BATCH_TRANSLATION_PROMPT.format(
        source_lang=source_lang,
        target_lang=target_lang,
        texts=json.dumps(non_empty_texts, ensure_ascii=False),
    )
    
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "You are a professional subtitle translator. Always respond with valid JSON arrays."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    response = _perform_request("POST", url, headers=headers, payload=payload, timeout=config.timeout)
    
    if not isinstance(response, dict):
        raise LLMClientError("Unexpected response from translation API")
    
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMClientError("Translation response did not include choices")
    
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise LLMClientError("Translation response message was invalid")
    
    content = message.get("content")
    if not isinstance(content, str):
        raise LLMClientError("Translation response did not include text content")
    
    # Parse JSON response
    try:
        # Try to extract JSON array from the response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            translated = json.loads(json_match.group())
        else:
            translated = json.loads(content)
    except json.JSONDecodeError:
        # Fallback: split by newlines
        translated = [line.strip() for line in content.strip().split('\n') if line.strip()]
    
    if not isinstance(translated, list):
        raise LLMClientError("Translation response was not a list")
    
    # Map translated texts back to original positions
    result = [""] * len(texts)
    for i, idx in enumerate(non_empty_indices):
        if i < len(translated):
            result[idx] = str(translated[i]).strip()
    
    return result


def parse_srt_content(content: str) -> List[SubtitleEntry]:
    """Parse SRT content into subtitle entries."""
    blocks = re.split(r'\n\s*\n', content.strip())
    entries = []
    
    for block in blocks:
        if not block.strip():
            continue
        
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        try:
            index = int(lines[0].strip())
            timestamp_match = re.match(
                r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})',
                lines[1].strip()
            )
            if not timestamp_match:
                continue
            
            start_time = timestamp_match.group(1)
            end_time = timestamp_match.group(2)
            text = '\n'.join(lines[2:]).strip()
            
            entries.append(SubtitleEntry(
                index=index,
                start_time=start_time,
                end_time=end_time,
                original_text=text,
            ))
        except (ValueError, IndexError):
            continue
    
    return entries


def format_srt_bilingual(
    entries: List[SubtitleEntry],
    bilingual_mode: str = "original_on_top",
) -> str:
    """Format subtitle entries as bilingual SRT.
    
    bilingual_mode options:
    - "original_on_top": Original text on top, translation below
    - "translation_on_top": Translation on top, original text below
    - "translation_only": Only show translation
    """
    lines = []
    
    for entry in entries:
        lines.append(str(entry.index))
        lines.append(f"{entry.start_time} --> {entry.end_time}")
        
        if bilingual_mode == "translation_only":
            lines.append(entry.translated_text or entry.original_text)
        elif bilingual_mode == "translation_on_top":
            if entry.translated_text:
                lines.append(entry.translated_text)
            lines.append(entry.original_text)
        else:  # original_on_top
            lines.append(entry.original_text)
            if entry.translated_text:
                lines.append(entry.translated_text)
        
        lines.append("")  # Empty line separator
    
    return '\n'.join(lines)


def format_ass_bilingual(
    entries: List[SubtitleEntry],
    bilingual_mode: str = "original_on_top",
) -> str:
    """Format subtitle entries as bilingual ASS.
    
    bilingual_mode options:
    - "original_on_top": Original text on top, translation below
    - "translation_on_top": Translation on top, original text below
    - "translation_only": Only show translation
    """
    lines = []
    
    # ASS header
    lines.append("[Script Info]")
    lines.append("Title: Generated by Abogen (Bilingual)")
    lines.append("ScriptType: v4.00+")
    lines.append("")
    lines.append("[V4+ Styles]")
    lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    # Style for original text (white)
    lines.append("Style: Original,Arial,24,&H00FFFFFF,&H00808080,&H00000000,&H00404040,0,0,0,0,100,100,0,0,3,2,0,5,10,10,30,1")
    # Style for translated text (yellow)
    lines.append("Style: Translated,Arial,20,&H0000FFFF,&H00808080,&H00000000,&H00404040,0,0,0,0,100,100,0,0,3,2,0,5,10,10,10,1")
    lines.append("")
    lines.append("[Events]")
    lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    
    for entry in entries:
        # Convert SRT timestamp to ASS format
        start_ass = _srt_to_ass_timestamp(entry.start_time)
        end_ass = _srt_to_ass_timestamp(entry.end_time)
        
        if bilingual_mode == "translation_only":
            if entry.translated_text:
                lines.append(f"Dialogue: 0,{start_ass},{end_ass},Translated,,0000,0000,0000,,{entry.translated_text}")
            else:
                lines.append(f"Dialogue: 0,{start_ass},{end_ass},Original,,0000,0000,0000,,{entry.original_text}")
        elif bilingual_mode == "translation_on_top":
            if entry.translated_text:
                lines.append(f"Dialogue: 0,{start_ass},{end_ass},Translated,,0000,0000,0000,,{entry.translated_text}")
            lines.append(f"Dialogue: 1,{start_ass},{end_ass},Original,,0000,0000,0000,,{entry.original_text}")
        else:  # original_on_top
            lines.append(f"Dialogue: 1,{start_ass},{end_ass},Original,,0000,0000,0000,,{entry.original_text}")
            if entry.translated_text:
                lines.append(f"Dialogue: 0,{start_ass},{end_ass},Translated,,0000,0000,0000,,{entry.translated_text}")
    
    return '\n'.join(lines)


def _srt_to_ass_timestamp(srt_time: str) -> str:
    """Convert SRT timestamp (HH:MM:SS,mmm) to ASS format (H:MM:SS.cc)."""
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', srt_time)
    if not match:
        return srt_time
    
    h, m, s, ms = match.groups()
    centiseconds = int(ms) // 10
    return f"{int(h)}:{m}:{s}.{centiseconds:02d}"


def translate_subtitles(
    entries: List[SubtitleEntry],
    config: TranslationConfig,
    progress_callback: Optional[Any] = None,
) -> List[SubtitleEntry]:
    """Translate all subtitle entries using the configured LLM.
    
    Args:
        entries: List of subtitle entries to translate
        config: Translation configuration
        progress_callback: Optional callback function(current, total)
    
    Returns:
        List of subtitle entries with translations added
    """
    if not config.is_configured():
        raise LLMClientError("Translation configuration is incomplete")
    
    if not entries:
        return []
    
    total = len(entries)
    batch_size = config.batch_size
    
    for i in range(0, total, batch_size):
        batch = entries[i:i + batch_size]
        texts = [entry.original_text for entry in batch]
        
        try:
            translated = translate_batch_texts(config, texts)
            for j, entry in enumerate(batch):
                if j < len(translated):
                    entry.translated_text = translated[j]
        except Exception:
            # Fallback to single translation on batch failure
            for entry in batch:
                try:
                    entry.translated_text = translate_single_text(config, entry.original_text)
                except Exception:
                    entry.translated_text = entry.original_text
        
        if progress_callback:
            progress_callback(min(i + batch_size, total), total)
    
    return entries
