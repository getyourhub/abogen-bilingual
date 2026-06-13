# Bilingual Subtitle Translation Feature

## Overview

This feature adds bilingual subtitle support to Abogen, allowing users to generate subtitles with both original text and translations. The translation is performed using LLM (Large Language Model) APIs, supporting both cloud providers (OpenAI, etc.) and local models (Ollama, LM Studio, etc.).

## Files Modified/Created

### New Files
1. **`abogen/subtitle_translator.py`** - Core translation module
   - `TranslationConfig` - Configuration for translation
   - `SubtitleEntry` - Subtitle entry with original and translated text
   - `translate_single_text()` - Translate a single text
   - `translate_batch_texts()` - Translate multiple texts in one API call
   - `translate_subtitles()` - Translate all subtitle entries
   - `format_srt_bilingual()` - Format bilingual SRT output
   - `format_ass_bilingual()` - Format bilingual ASS output

### Modified Files
1. **`abogen/webui/conversion_runner.py`**
   - Updated `SubtitleWriter` class to support bilingual output
   - Added `bilingual_mode` and `translation_config` parameters
   - Added translation logic in `close()` method

2. **`abogen/webui/service.py`**
   - Added bilingual subtitle fields to `Job` and `PendingJob` dataclasses
   - Updated `enqueue()` method to accept translation parameters
   - Updated `_serialize_job()` and `_deserialize_job()` for persistence

3. **`abogen/webui/routes/utils/service.py`**
   - Updated `submit_job()` to pass bilingual subtitle settings

4. **`abogen/webui/routes/utils/form.py`**
   - Updated `apply_book_step_form()` to capture bilingual settings
   - Updated `build_pending_job_from_extraction()` to include bilingual settings

5. **`abogen/webui/templates/partials/new_job_step_book.html`**
   - Added bilingual subtitle settings UI section
   - Added JavaScript to toggle translation settings visibility

## How to Use

### 1. Enable Bilingual Subtitles
When creating a new job, scroll to the "Bilingual subtitles (translation)" section and select a mode:
- **Original on top, translation below** - Shows original text first, then translation
- **Translation on top, original below** - Shows translation first, then original text
- **Translation only** - Shows only the translated text

### 2. Configure Translation Settings
After enabling bilingual mode, configure the translation settings:

- **LLM API Base URL** - The endpoint for your LLM provider:
  - OpenAI: `https://api.openai.com`
  - Ollama: `http://localhost:11434`
  - LM Studio: `http://localhost:1234`
  - Other OpenAI-compatible endpoints

- **API Key** - Your API key (leave empty for local models)

- **Model** - The model to use for translation:
  - OpenAI: `gpt-4o-mini`, `gpt-4o`, etc.
  - Ollama: `llama3`, `qwen2`, `mistral`, etc.
  - LM Studio: Model name loaded in the UI

- **Source Language** - The language of the original subtitles
- **Target Language** - The language to translate to

- **Timeout** - Maximum time to wait for translation (in seconds)
- **Batch Size** - Number of subtitles to translate in one API call

### 3. Supported Languages
The translation supports all languages that the LLM can handle, including:
- English, Chinese, Japanese, Korean
- French, German, Spanish, Portuguese
- Russian, Arabic, Hindi, Italian
- And many more...

## Technical Details

### Translation Process
1. Subtitles are generated as usual by the TTS engine
2. When the subtitle file is closed, translation begins
3. Subtitles are sent to the LLM in batches for efficiency
4. Translated text is stored alongside original text
5. The final subtitle file is written in bilingual format

### Batch Translation
To improve efficiency, the feature supports batch translation:
- Multiple subtitles are sent in one API call
- The LLM returns a JSON array of translations
- Default batch size is 10 (configurable from 1 to 50)

### Error Handling
- If translation fails, the system falls back to single subtitle translation
- If all translation attempts fail, the original text is preserved
- Translation errors are logged but don't prevent audio generation

## Example Configuration

### Using Ollama (Local)
```
Base URL: http://localhost:11434
API Key: (leave empty)
Model: qwen2.5:7b
Source: English
Target: Chinese
```

### Using OpenAI
```
Base URL: https://api.openai.com
API Key: sk-...
Model: gpt-4o-mini
Source: English
Target: Chinese
```

### Using LM Studio
```
Base URL: http://localhost:1234
API Key: (leave empty)
Model: (model loaded in LM Studio)
Source: English
Target: Chinese
```

## Output Formats

### SRT Bilingual Example
```
1
00:00:01,000 --> 00:00:03,000
Hello, how are you?
你好，你好吗？

2
00:00:03,500 --> 00:00:05,500
I'm doing well, thank you.
我很好，谢谢。
```

### ASS Bilingual Example
The ASS format uses two styles:
- `Original` - White text, positioned lower
- `Translated` - Yellow text, positioned higher

## Notes

- Translation adds processing time depending on the number of subtitles and LLM speed
- For best results with local models, use models with good translation capabilities (e.g., Qwen2.5, Llama 3)
- The translation is performed after all audio is generated, so it doesn't affect TTS quality
- API keys are stored per-job and not saved in global settings for security
