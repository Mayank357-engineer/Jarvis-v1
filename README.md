J.A.R.V.I.S v1 — Offline-First Personal AI Assistant
J.A.R.V.I.S v1 is a Python-based personal assistant project that combines a locally hosted language model, voice input and output, a desktop GUI, tool/function calling, local key-value memory, face authentication, and an ESP32 serial-display integration.

The project is offline-first, rather than fully offline in every mode: the Gemini brain, Google Cloud Speech mode, web search/news, and first-time model downloads require internet access.
Source snapshot note: This README describes the code in the uploaded Jarvis_version1.zip. You confirmed that the Instruct-model version in this snapshot is the version you currently run and that J.A.R.V.I.S works on your machine. The review notes below are specific observations from static inspection of the uploaded files; they may affect particular tools or configurations rather than preventing the application from running generally. Verify those paths before advertising each optional feature as working in every mode.

Features in this source snapshot
- Local language model: main.py starts llama-server and points an OpenAI-compatible client at http://127.0.0.1:8080/v1. The exact model argument in the uploaded source is LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M, with a 4,096-token context setting. This is the Instruct model, not a Thinking-named model.
- Optional online brain: gemini_UPDATED.py uses the google-genai SDK and configures the model ID gemini-3.8-flash.
- Speech input: Faster-Whisper base runs locally on CPU with int8 compute. A cloud speech-recognition path uses Google Cloud Speech with language code en-IN.
- Speech output: pyttsx3 provides local text-to-speech.
- Wake-word check: the offline main loop checks recognized words against “jarvis” using SequenceMatcher and a threshold of 0.70.
- Tools and actions: current code includes time retrieval, DuckDuckGo web search, cached search-result/webpage reading, persistent key-value memory functions, browser opening, a small music URL map, a news command placeholder, and an ESP32 display command.
- Memory: memory.py stores key/value facts in a memory.json file in the process working directory. The offline chat history keeps up to 10 message entries in memory during the current process. The local model server is configured with -c 4096; the code does not enforce a 1,000-token application memory window. The Gemini complete() function creates a fresh message list for each call, so it does not maintain multi-turn chat history between separate GUI commands in this snapshot.
- Face authentication: face_auth.py uses OpenCV YuNet/SFace models. On first use, the models are downloaded and cached under the user's local application-data directory. The app collects an owner profile and a user-chosen fallback password (minimum 8 characters); the password is stored as a salted PBKDF2-HMAC-SHA256 hash. Face embeddings and profiles are stored locally in users.json under the app-data directory.
- Desktop GUI: GUI_v2_COMPLETE_ORANGE_JARVIS.py uses PySide6, PyOpenGL, and psutil for a custom animated interface and system monitoring.
- ESP32 integration: esp32/controller.py sends a text line over serial at 115200 baud. The current source hardcodes COM4; the command in main.py truncates messages to 32 characters.
Repository structure
Jarvis_version1/
├── GUI_v2_COMPLETE_ORANGE_JARVIS.py  # PySide6 / PyOpenGL desktop GUI
├── main.py                           # Local model server, offline commands, STT/TTS
├── gemini_UPDATED.py                 # Optional Gemini brain and function-calling loop
├── jarvis_settings.py                # Brain/STT mode state
├── jarvis_tools.py                   # Tool schemas/implementations used by main.py
├── jarvis_tools_COMPLETE.py          # Separate tool layer used by Gemini
├── memory.py                         # Local JSON key/value memory
├── music_playlist.py                 # Supported music-name-to-URL mappings
├── face_auth.py                      # Local face authentication and password fallback
├── esp32/
│   ├── __init__.py
│   └── controller.py                 # Serial messages to ESP32
├── test_esp32.py                     # Simple serial/LCD test script
├── requirements.txt
└── requirements-face-auth.txt
Requirements
- Windows is the environment targeted by the uploaded project (the GUI uses a Windows-compatible serial-port default, COM4).
- Python and the Python packages listed in requirements.txt.
- A llama-server executable from llama.cpp available on PATH. The code invokes llama-server directly and asks it to retrieve the configured GGUF model using -hf.
- A microphone for voice input and a camera for face enrollment/unlock.
- An ESP32 and compatible serial/LCD firmware for the hardware-display feature.
- API configuration and credentials for the optional Gemini, News API, and Google Cloud Speech paths.
The first launch may need internet access to download the language-model files through llama-server -hf and the face-detection/recognition ONNX models from the OpenCV Zoo. Once cached, the face models are read from the local app-data folder.
Installation (Windows / PowerShell)
1. Clone or download this repository.
2. Open a terminal in the project root.
3. Create and activate a virtual environment:
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
4. Install llama-server separately and make sure llama-server --help works from the same terminal. The executable is not a Python package and is not installed by requirements.txt.
5. Configure API credentials securely before using online/cloud features. Do not commit real API keys. The current source snapshot still has placeholder strings and does not yet consistently read keys from environment variables; see “Known issues before public release”.
6. Connect your ESP32 and update the serial port in esp32/controller.py (and test_esp32.py, if used) if it is not COM4.
7. Launch the GUI:
   python GUI_v2_COMPLETE_ORANGE_JARVIS.py
8. On first launch, follow the face-enrollment prompt and choose a fallback password of at least eight characters. Face-auth data is stored locally, not in the repository.
Startup warning: main.py launches llama-server during module import and waits for the server's /v1/models endpoint without a timeout. If llama-server is missing or fails to start, the application can wait indefinitely. Ensure the executable works before launching the GUI.

Usage examples
Commands handled directly in main.py include:
- open YouTube
- open Google
- open GitHub
- play parvati or play nirvanashatkam (the names configured in music_playlist.py)
- news (requires valid News API configuration)
- sleep
- stop
- display Hello from Jarvis (sends up to 32 characters to the ESP32)
Other requests are passed to the local model and may use available tools. In the GUI, select the offline LFM2.5 brain or online Gemini brain and choose local Whisper or cloud speech recognition.
Privacy and credentials
- Keep .env, API credentials, face profiles/embeddings, generated memory data, model weights, and local logs out of public GitHub.
- Face-authentication information is stored under %LOCALAPPDATA%\Jarvis\face_auth\ on Windows (including users.json and cached ONNX models).
- memory.json contains user-specific remembered facts and should remain local. The memory.json included in the uploaded ZIP contains sample values; remove it from the public repository.
- The checked-in source should use environment variables or another local-only configuration mechanism for secrets before real API keys are added.
Potential issues to verify before public release
1. Gemini key placeholder validation: gemini_UPDATED.py currently sets GEMINI_API_KEY to the text Paste your Gemini API key here, while the validation check looks for a different placeholder (PASTE_YOUR_GEMINI_API_KEY_HERE). Online mode may attempt to initialize with the placeholder rather than give the intended missing-key error.
2. API-key handling: the News API URL contains YOUR_NEWSAPI_KEY, and Gemini uses a source-code placeholder. No actual key was found in the uploaded snapshot. Before public release, consider switching both to environment variables and documenting the setup with an .env.example file.
3. Gemini memory integration to verify: jarvis_tools_COMPLETE.py imports load_memory and save_memory from memory.py, but the uploaded memory.py only defines remember_fact and recall_memory. In this snapshot, the Gemini tool layer appears to catch that import mismatch and disable its persistent-memory integration. This does not mean the entire app cannot run; test this specific feature in Gemini mode before describing it as supported.
4. Offline tool selection issues: in main.py, the string literals "Who is" and "search" are adjacent without a comma, so Python concatenates them. The standalone search keyword is therefore missing from the web-intent list. Also, the offline model gets only the get_time tool unless the command matches web_keywords; memory-only requests such as “remember this” do not reliably make the memory tools available.
5. Different webpage tool behavior: jarvis_tools.py fetches a webpage and extracts its text, while jarvis_tools_COMPLETE.py returns the snippet cached from DuckDuckGo instead of fetching the full page. The two modes therefore do not behave identically for read_webpage.
6. News command to configure: fetchNews() contains a placeholder API key in the URL and has no request timeout/status check. Configure the key locally before testing news, and consider adding timeout/status handling.
7. Memory data in ZIP: remove memory.json from the public source copy and ignore it in Git. Runtime memory should be created locally when needed.
8. Module-import side effect: importing main.py starts the local server and waits for it to become ready. A startup timeout and cleanup on errors would make the app safer to launch.
9. Stale filename in Gemini comments: some comments tell the reader to edit gemini.py, but the uploaded file is named gemini_UPDATED.py.
10. Password default mismatch: this snapshot does not contain a hardcoded default PIN of 128; the GUI asks the owner to create a fallback password with a minimum length of eight characters.
Dependency note
The requirements.txt in the uploaded ZIP appears to be UTF-16 encoded and includes a full environment freeze with transitive and apparently unused packages (including both PySide6 and PyQt6). A cleaner UTF-8 dependency list is supplied alongside this README. It is based on imports in this snapshot and versions shown in the existing freeze, but should still be tested in a fresh virtual environment before the repository is described as reproducibly installable.
Project status
This is a personal, evolving v1 project. You confirmed that this model version runs on your own machine. A fresh clone will still need local setup for the model server, credentials, hardware ports, camera/microphone access, and downloaded models. The potential integration issues listed above are static-review findings for specific code paths; check them against the features you intend to advertise before publishing.
