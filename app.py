import os
import sys
import json
import queue
import tempfile
import threading
from pathlib import Path

from flask import Flask, render_template, request, jsonify, Response, send_file
import autogen
import autogen as ag2

from utils.language_detector import detect_language
from utils.file_scanner import scan_project
from utils.llm_config import LLM_CONFIG
from agents.bug_detector import create_bug_detector
from agents.style_checker import create_style_checker
from agents.security_auditor import create_security_auditor
from agents.summarizer import create_summarizer
from agents.user_proxy import create_user_proxy, create_spec_proxy
from tools.save_report import save_review_to_file

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Global progress queue for SSE
progress_queue = queue.Queue()


def make_review_message(filepath, content, language):
    return (
        f"Please review the following {language} code from '{filepath}':\n\n"
        f"```\n{content}\n```"
    )


def speaker_selection_func(last_speaker, groupchat):
    """Enforce strict agent execution order with tool-call round-trip handling."""
    name = last_speaker.name
    agents = {a.name: a for a in groupchat.agents}
    messages = groupchat.messages

    if name == "Summarizer":
        last_msg = messages[-1] if messages else {}
        if last_msg.get("tool_calls") or last_msg.get("function_call"):
            return agents["User_Proxy"]
        return None

    if name == "User_Proxy":
        if any(m.get("name") == "Summarizer" for m in messages):
            return agents["Summarizer"]
        return agents["Bug_Detector"]

    order = ["User_Proxy", "Bug_Detector", "Style_Checker", "Security_Auditor", "Summarizer"]
    if name in order[:-1]:
        return agents[order[order.index(name) + 1]]
    return None


def run_single_review(filepath, content, language):
    """Run the full 5-agent GroupChat for a single file."""
    progress_queue.put({"step": "Bug_Detector", "status": "running"})

    user_proxy = create_user_proxy()
    bug_detector = create_bug_detector()
    style_checker = create_style_checker()
    security_auditor = create_security_auditor()
    summarizer = create_summarizer()

    ag2.register_function(
        save_review_to_file,
        caller=summarizer,
        executor=user_proxy,
        name="save_review_to_file",
        description="Save the code review report to review_output.md",
    )

    groupchat = autogen.GroupChat(
        agents=[user_proxy, bug_detector, style_checker, security_auditor, summarizer],
        messages=[],
        speaker_selection_method=speaker_selection_func,
        max_round=10,
    )
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=LLM_CONFIG)

    message = make_review_message(filepath, content, language)
    user_proxy.initiate_chat(manager, message=message, silent=True)

    progress_queue.put({"step": "complete", "status": "done"})


def run_project_review(files):
    """Run project mode review across multiple files."""
    n = len(files)
    all_findings = []

    for i, (filepath, content, language) in enumerate(files):
        progress_queue.put({
            "step": f"File {i + 1}/{n}: {filepath}",
            "status": "running"
        })

        spec_proxy = create_spec_proxy()
        bug_detector = create_bug_detector()
        code_msg = make_review_message(filepath, content, language)
        bug_result = spec_proxy.initiate_chat(bug_detector, message=code_msg, max_turns=2, silent=True)
        bug_findings = (
            bug_result.chat_history[-1]["content"]
            if bug_result.chat_history
            else "No bugs found."
        )

        spec_proxy2 = create_spec_proxy()
        style_checker = create_style_checker()
        style_result = spec_proxy2.initiate_chat(style_checker, message=code_msg, max_turns=2, silent=True)
        style_findings = (
            style_result.chat_history[-1]["content"]
            if style_result.chat_history
            else "No style issues found."
        )

        spec_proxy3 = create_spec_proxy()
        security_auditor = create_security_auditor()
        sec_result = spec_proxy3.initiate_chat(security_auditor, message=code_msg, max_turns=2, silent=True)
        security_findings = (
            sec_result.chat_history[-1]["content"]
            if sec_result.chat_history
            else "No security issues found."
        )

        all_findings.append({
            "filepath": filepath,
            "language": language,
            "bugs": bug_findings,
            "style": style_findings,
            "security": security_findings,
        })

    progress_queue.put({"step": "Summarizing", "status": "running"})

    # Run Summarizer
    user_proxy = create_user_proxy()
    summarizer = create_summarizer()

    ag2.register_function(
        save_review_to_file,
        caller=summarizer,
        executor=user_proxy,
        name="save_review_to_file",
        description="Save the code review report to review_output.md",
    )

    parts = [f"Please produce a combined project review report for the following {n} file(s).\n"]
    for idx, f in enumerate(all_findings):
        parts.append(f"\n=== File {idx + 1}/{n}: {f['filepath']} ({f['language']}) ===\n")
        parts.append(f"Bug_Detector findings:\n{f['bugs']}\n\n")
        parts.append(f"Style_Checker findings:\n{f['style']}\n\n")
        parts.append(f"Security_Auditor findings:\n{f['security']}\n")
    combined = "".join(parts)

    def project_summary_speaker_selection(last_speaker, groupchat):
        agents = {a.name: a for a in groupchat.agents}
        messages = groupchat.messages
        name = last_speaker.name

        if name == "Summarizer":
            last_msg = messages[-1] if messages else {}
            if last_msg.get("tool_calls") or last_msg.get("function_call"):
                return agents["User_Proxy"]
            return None

        return agents["Summarizer"]

    groupchat = autogen.GroupChat(
        agents=[user_proxy, summarizer],
        messages=[],
        speaker_selection_method=project_summary_speaker_selection,
        max_round=4,
    )
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=LLM_CONFIG)
    user_proxy.initiate_chat(manager, message=combined, silent=True)

    progress_queue.put({"step": "complete", "status": "done"})


def extract_verdict(report):
    """Extract verdict from the report (PASS, PASS WITH NOTES, NEEDS REVISION)."""
    report_upper = report.upper()
    if "NEEDS REVISION" in report_upper:
        return "NEEDS REVISION"
    elif "PASS WITH NOTES" in report_upper:
        return "PASS WITH NOTES"
    elif "PASS" in report_upper:
        return "PASS"
    return "UNKNOWN"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/review/inline", methods=["POST"])
def review_inline():
    """Review inline code snippet."""
    try:
        data = request.get_json()
        code = data.get("code", "").strip()
        language = data.get("language", "auto")

        if not code:
            return jsonify({"error": "No code provided"}), 400

        progress_queue.put({"step": "Detecting Language", "status": "running"})

        if language == "auto":
            language = detect_language(code=code, ext=None)
            if language == "UNKNOWN":
                return jsonify({"error": "Could not detect language"}), 400

        progress_queue.put({"step": "Detecting Language", "status": "done"})

        run_single_review("Inline snippet", code, language)

        # Read the report
        if os.path.exists("review_output.md"):
            with open("review_output.md", "r", encoding="utf-8") as f:
                report = f.read()
                # Remove the prepended header
                if report.startswith("# CodeSentinel Review Report\n\n"):
                    report = report[len("# CodeSentinel Review Report\n\n"):]
        else:
            report = ""

        verdict = extract_verdict(report)

        return jsonify({
            "report": report,
            "language": language,
            "verdict": verdict,
            "saved_to": "review_output.md"
        })

    except Exception as e:
        return jsonify({"error": f"Agent error: {str(e)}"}), 500


@app.route("/review/file", methods=["POST"])
def review_file():
    """Review an uploaded file."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        language = request.form.get("language", "auto")

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=Path(file.filename).suffix) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        try:
            progress_queue.put({"step": "Detecting Language", "status": "running"})

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            if language == "auto":
                ext = Path(file.filename).suffix
                language = detect_language(code=content, ext=ext)
                if language == "UNKNOWN":
                    return jsonify({"error": "Could not detect language"}), 400

            progress_queue.put({"step": "Detecting Language", "status": "done"})

            run_single_review(file.filename, content, language)

            if os.path.exists("review_output.md"):
                with open("review_output.md", "r", encoding="utf-8") as f:
                    report = f.read()
                    if report.startswith("# CodeSentinel Review Report\n\n"):
                        report = report[len("# CodeSentinel Review Report\n\n"):]
            else:
                report = ""

            verdict = extract_verdict(report)

            return jsonify({
                "report": report,
                "language": language,
                "verdict": verdict,
                "saved_to": "review_output.md"
            })

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        return jsonify({"error": f"Agent error: {str(e)}"}), 500


@app.route("/review/project", methods=["POST"])
def review_project():
    """Review a project directory."""
    try:
        data = request.get_json()
        path = data.get("path", "").strip()

        if not path:
            return jsonify({"error": "No path provided"}), 400

        if not os.path.isdir(path):
            return jsonify({"error": "Path not found"}), 400

        progress_queue.put({"step": "Scanning", "status": "running"})

        files, was_capped = scan_project(path)

        if not files:
            return jsonify({"error": "No reviewable source files found"}), 400

        progress_queue.put({"step": "Scanning", "status": "done"})

        run_project_review(files)

        if os.path.exists("review_output.md"):
            with open("review_output.md", "r", encoding="utf-8") as f:
                report = f.read()
                if report.startswith("# CodeSentinel Review Report\n\n"):
                    report = report[len("# CodeSentinel Review Report\n\n"):]
        else:
            report = ""

        verdict = extract_verdict(report)

        return jsonify({
            "report": report,
            "verdict": verdict,
            "saved_to": "review_output.md"
        })

    except Exception as e:
        return jsonify({"error": f"Agent error: {str(e)}"}), 500


@app.route("/progress")
def progress():
    """SSE endpoint for streaming progress updates."""
    def generate():
        while True:
            try:
                event = progress_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("step") == "complete":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'step': 'idle', 'status': 'waiting'})}\n\n"
                break

    return Response(generate(), mimetype="text/event-stream")


@app.route("/download")
def download():
    """Download the review_output.md file."""
    if os.path.exists("review_output.md"):
        return send_file("review_output.md", as_attachment=True, download_name="review_output.md")
    return jsonify({"error": "Report not found"}), 404


SAMPLE_FILES = {
    "test_sample.py",
    "test_sample.js",
    "TestSample.java",
    "TestSample.cs",
}


@app.route("/sample/<filename>")
def download_sample(filename):
    """Download a sample test file."""
    if filename not in SAMPLE_FILES:
        return jsonify({"error": "File not found"}), 404
    tests_dir = os.path.join(os.path.dirname(__file__), "tests")
    file_path = os.path.join(tests_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
