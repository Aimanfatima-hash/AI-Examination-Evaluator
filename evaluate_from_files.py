
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from docx import Document
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def read_marking_scheme(scheme_path):
    """Extract text from a DOCX or PDF marking scheme."""

    scheme_path = Path(scheme_path)
    extension = scheme_path.suffix.lower()

    if extension == ".docx":
        doc = Document(scheme_path)

        text = "\n".join(
            p.text for p in doc.paragraphs if p.text.strip()
        )

        for table in doc.tables:
            for row in table.rows:
                text += "\n" + " | ".join(
                    cell.text for cell in row.cells
                )

        return text

    elif extension == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(scheme_path))

        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    raise ValueError("Unsupported marking scheme format.")


def evaluate_answer_sheet(
    answer_sheet_path,
    question_paper_path,
    marking_scheme_path
):

    answer_sheet_path = Path(answer_sheet_path)
    question_paper_path = Path(question_paper_path)
    marking_scheme_path = Path(marking_scheme_path)

    # Read the teacher's marking scheme
    scheme = read_marking_scheme(marking_scheme_path)

    if not scheme.strip():
        raise ValueError(
            "Could not extract text from the marking scheme."
        )

    print("Uploading answer sheet...")
    uploaded_answer = client.files.upload(
        file=str(answer_sheet_path)
    )

    print("Uploading question paper...")
    uploaded_question = client.files.upload(
        file=str(question_paper_path)
    )

    prompt = f"""
You are an AI assistant helping a teacher evaluate a Computer
Science examination.

You have been provided with:
1. The student's answer sheet.
2. The examination question paper.
3. The teacher's marking scheme below.

MARKING SCHEME:
{scheme}

EVALUATION RULES:

1. Identify questions using the question paper.
2. Evaluate the student's answers using the marking scheme.
3. Award partial marks when justified.
4. Accept equivalent wording and explanations.
5. Do not require students to reproduce answers word for word.
6. Do not invent missing answers or marks.
7. Do not assume an unreadable answer is incorrect.
8. Flag unclear handwriting, missing pages, missing answers,
   and uncertain assessments for teacher review.
9. Use the maximum marks specified in the marking scheme.
10. Do not make up a marking scheme if information is missing.

Return valid JSON only, using this structure:

{{
    "question1": {{
        "Marks": 1,
        "maximum_marks": 1,
        "reasoning": "Explanation of the awarded marks.",
        "review_required": false
    }},
    "question2": {{
        "Marks": 0.5,
        "maximum_marks": 2,
        "reasoning": "Explanation of partial credit.",
        "review_required": false
    }},
    "total_marks": 1.5,
    "maximum_total_marks": 3,
    "teacher_review_required": false
}}

IMPORTANT:
- Include every identifiable question and sub-question.
- Marks must be numbers, not strings.
- Do not invent missing questions.
- If an answer cannot be assessed, set review_required to true.
- Do not treat missing or unreadable answers as confirmed zero.
- Set teacher_review_required to true if any question needs review.
- Return JSON only, without Markdown code fences.
"""

    print("Sending documents to Gemini...")

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            uploaded_answer,
            uploaded_question,
            prompt
        ]
    )

    result_text = response.text or ""

    # Validate the JSON before saving it
    result_text = result_text.strip()

    if result_text.startswith("```"):
        result_text = result_text.replace("```json", "", 1)
        result_text = result_text.replace("```", "").strip()

    result = json.loads(result_text)

    # Save the evaluation
    results_folder = Path(__file__).parent / "Results"
    results_folder.mkdir(exist_ok=True)

    output_file = results_folder / (
        answer_sheet_path.stem + "_evaluation.json"
    )

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    print("Evaluation saved:", output_file)

    return result
