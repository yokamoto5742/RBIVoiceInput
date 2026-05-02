# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```powershell
uv sync                                                    # Install dependencies
python -m pytest tests/ -v --tb=short                     # Run all tests
python -m pytest tests/path/to/test_file.py -v --tb=short # Run single test file
python -m pytest tests/ -v --tb=short --cov=app --cov-report=html  # With coverage
pyright app service utils                                  # Type checking
python main.py                                             # Run app
python build.py                                            # Build RBIVoiceInput.exe
```

## Architecture

Windows-only voice input desktop app for Japanese dictation. Layered design:

```
app/          UI layer (Tkinter) — windows, tray, notifications, hotkey wiring
service/      Business logic — recording → transcription → docs output pipeline
external_service/  API wrappers — Google Cloud STT, Google Docs
utils/        Config, logging, .env loading
```

**Core recording flow:**
1. `KeyboardHandler` (app/) detects hotkey → `RecordingLifecycle.start_recording()`
2. `AudioRecorder` captures PCM frames; `RecordingTimer` auto-stops at 60s
3. `TranscriptionHandler` sends frames to `google_stt_api.transcribe_pcm()` in a thread
4. `TextTransformer` applies `data/replacements.txt` post-processing rules
5. `DocsOutput` appends result to Google Docs
6. All UI updates routed through `UIQueueProcessor` back to Tkinter main thread

**Entry points:** `main.py` → `app/application.py` → `service/recording_lifecycle.py`

## Key Configuration

- `utils/config.ini` — master config (audio, STT model, hotkeys, paths, logging)
- `data/replacements.txt` — CSV `incorrect,correct` post-processing rules
- `data/technical_terms.txt` — profession terms sent to STT as recognition hints
- `.env` (not in repo) — `GOOGLE_CREDENTIALS_JSON`, `GOOGLE_PROJECT_ID`, `GOOGLE_LOCATION`

## Coding Conventions

- Type hints required on all parameters and return values
- Functions ≤ 50 lines; single clear purpose per function/module
- Import order: stdlib → third-party → local (alphabetical within each group; `import` before `from`)
- UI-displayed messages must be in Japanese, defined as constants in `constants.py` — no magic strings
- Comments only for non-obvious logic, written in Japanese; minimal docstrings
