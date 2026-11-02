
import os
import uuid
import re
from pathlib import Path

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

from evaluate_from_files import evaluate_answer_sheet

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / "uploads"

app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

UPLOAD_FOLDER.mkdir(exist_ok=True)

ALLOWED_FILES = {
    "answer_sheet": {"pdf", "png", "jpg", "jpeg"},
    "question_paper": {"pdf"},
    "marking_scheme": {"pdf", "docx"}
}


def question_sort_key(row):
    """Sort Q2 before Q10 and keep sub-questions together."""
    parts = re.split(r"(\d+)", row["question"])
    return [
        int(part) if part.isdigit() else part.lower()
        for part in parts
    ]


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_files():
    saved_files = {}

    try:
        for field, allowed_extensions in ALLOWED_FILES.items():
            file = request.files.get(field)

            if not file or file.filename == "":
                return render_template(
                    "index.html",
                    message=f"Please upload the {field.replace('_', ' ')}."
                )

            filename = secure_filename(file.filename)
            extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

            if extension not in allowed_extensions:
                return render_template(
                    "index.html",
                    message=f"Invalid file type for {field.replace('_', ' ')}."
                )

            unique_name = f"{uuid.uuid4().hex}_{filename}"
            file_path = UPLOAD_FOLDER / unique_name

            file.save(file_path)
            saved_files[field] = str(file_path)

        print("Documents uploaded. Starting evaluation...")

        result = evaluate_answer_sheet(
            answer_sheet_path=saved_files["answer_sheet"],
            question_paper_path=saved_files["question_paper"],
            marking_scheme_path=saved_files["marking_scheme"]
        )

        # Prepare question-wise results for the dashboard.
        question_rows = []

        for key, value in result.items():
            if isinstance(value, dict) and "Marks" in value:
                question_rows.append({
                    "question": key.replace("question", "Q"),
                    "marks": value.get("Marks", 0),
                    "maximum": value.get("maximum_marks", 0),
                    "reasoning": value.get("reasoning", "No explanation provided."),
                    "review": value.get("review_required", False)
                })

        question_rows.sort(key=question_sort_key)

        total_marks = result.get("total_marks", 0)
        maximum_marks = result.get("maximum_total_marks", 0)

        percentage = (
            round((total_marks / maximum_marks) * 100, 2)
            if maximum_marks else 0
        )

        review_count = sum(
            1 for row in question_rows if row["review"]
        )

        summary = {
            "total_marks": total_marks,
            "maximum_marks": maximum_marks,
            "percentage": percentage,
            "review_count": review_count,
            "question_count": len(question_rows)
        }

        print("Evaluation completed.")

        return render_template(
            "index.html",
            message="Evaluation completed successfully!",
            question_rows=question_rows,
            summary=summary,
            teacher_review_required=result.get(
                "teacher_review_required", False
            )
        )

    except Exception as error:
        app.logger.exception("Evaluation failed")

        return render_template(
            "index.html",
            message=f"Evaluation could not be completed: {error}"
        )


if __name__ == "__main__":
    app.run(debug=True)


