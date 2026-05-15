# CodeSentinel

CodeSentinel is a multi-agent code review assistant that analyzes source code for bugs, style issues, and security risks. It supports both a web UI and a CLI, and can review inline code, a single file, or an entire project folder.

## Authors

- Hoan Le — Hoan.Le@student.oulu.fi — Student ID: 2504960
- Khoa Dinh — t0dida00@students.oamk.fi — Student ID: 2508783
- Van Nguyen — Van.M.Nguyen@student.oulu.fi — Student ID: 2506205

## Tech Stack

- Python
- Flask
- AG2 / AutoGen
- OpenAI-compatible client
- Server-Sent Events (SSE) for live progress updates
- HTML, CSS for the frontend

## Features

- Multi-agent review pipeline with specialized agents for bugs, style, and security
- Automatic programming language detection
- Web UI for inline snippets, file uploads, and project path reviews
- CLI mode for terminal-based reviews
- Real-time review progress in the browser
- Markdown report generation with verdict summaries
- Downloadable `review_output.md` report
- Project scanning with filtering for code files and large-file limits

## Project Structure

```text
.
├── agents/          # Agent definitions and prompts
├── static/          # Frontend assets
├── templates/       # Flask templates
├── tests/           # Sample files for testing
├── tools/           # Tool functions used by agents
├── utils/           # Config, scanning, input handling, language detection
├── app.py           # Flask web app entry point
├── main.py          # CLI entry point
└── review_output.md # Generated review report
```

## Setup

### Prerequisites

- Python 3.10 or newer

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Set these values in `.env`:

```env
LLM_BASE_URL=https://5f5832nb90.execute-api.eu-central-1.amazonaws.com/v1
```

The model and API key are defined in code:

```text
model: openai/gpt-4.1-mini
api_key: no-key
```

## How to Build and Run

### Build / Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

### Web App

```bash
python app.py
```

Then open `http://localhost:5000`.

### CLI

Review a single file:

```bash
python main.py --file path/to/file.py
```

Review inline code:

```bash
python main.py --inline
```

Review a project folder:

```bash
python main.py --project path/to/project
```

## How It Works

CodeSentinel routes the input through a small team of agents:

- `User_Proxy` starts the review flow and executes the report-saving tool call
- `Bug_Detector` checks for logic errors and runtime issues
- `Style_Checker` checks coding style and convention problems
- `Security_Auditor` checks for vulnerabilities and risky patterns
- `Summarizer` combines all findings into a final report

The generated report is saved to `review_output.md`.

## Testing

The `tests/` folder contains sample files with intentional issues you can use to try the reviewer.

Example:

```bash
python main.py --file tests/test_sample.py
```

## Notes

- The app is designed for local use
- Review quality depends on the configured LLM
- Submitted code is analyzed as text; it is not executed
- Uploaded files are limited to 16 MB in the web app
- Project review mode skips oversized files and caps the number of reviewed files
