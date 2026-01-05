# Live Voice Agent - Gemini 2.5 Flash

A low-latency voice agent using Google's Gemini 2.5 Flash Native Audio model and Pipecat.

## 🚀 Quick Start (macOS/Linux)

We have automated the setup process for you.

### 1. Setup

Run this script once to set up the Python environment, install dependencies, and prepare the client.

```bash
chmod +x setup_mac.sh start.sh
./setup_mac.sh
```

### 2. Start

Run this command to start both the Python backend and the React frontend.

```bash
./start.sh
```

- **Backend**: http://localhost:7860
- **Frontend**: http://localhost:5173

## 🛠 Manual Setup

If you prefer to set things up manually:

**Server:**

1. `python3 -m venv venv`
2. `source venv/bin/activate`
3. `pip install -r server/requirements.txt`
4. Copy `server/env.example` to `server/.env` and add your `GOOGLE_API_KEY`.
5. `python server/server.py`

**Client:**

1. `cd client`
2. `npm install`
3. `npm run dev`

## 🤖 Customization

### System Prompt

You can customize the bot's personality and instructions by editing:
`server/system_prompt.txt`

The bot is configured to read this file dynamically.

### Model

Using `gemini-2.5-flash-native-audio-preview-12-2025`.

---

Happy coding! 🎉
