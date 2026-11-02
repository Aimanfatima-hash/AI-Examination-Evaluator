import time  
from pathlib import Path
from dotenv import load_dotenv
from docx import Document
from google import genai
import os

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

BASE = Path(__file__).parent
SHEETS = BASE / "Answer Sheets"
REFERENCES = BASE / "Ques Paper & Answer Key"

# Find one answer sheet and the marking scheme document
pdf_path = next(SHEETS.glob("*.pdf"))
docx_path = next(REFERENCES.glob("*.docx"))

doc = Document(docx_path)
scheme = "\n".join(p.text for p in doc.paragraphs if p.text.strip()) 

# Include table text too, if the document contains tables
for table in doc.tables:
    for row in table.rows:
        scheme += "\n" + " | ".join(cell.text for cell in row.cells)

print("Uploading:", pdf_path.name)
print("PDF path:", pdf_path.resolve())
print("Scheme document:", docx_path.name)
uploaded_pdf = client.files.upload(file=str(pdf_path))

prompt = f"""
You are an AI assistant helping a teacher evaluate a Computer Science exam.

Read the attached scanned answer-sheet PDF. Use the answer key and
marking scheme below to evaluate the student's answers.

MARKING SCHEME:
{scheme}

Rules:
1. Evaluate each identifiable question against its stated maximum marks.
2. Give partial credit when the marking criteria allow it.
3. Do not guess answers that are unreadable or unclear.
4. Mark uncertain answers as NEEDS_TEACHER_REVIEW.
5. Do not invent missing questions or marks.
6. Return JSON with:
   question_number, maximum_marks, awarded_marks, reason, review_required.
7. At the end, report the total marks awarded and total marks assessed.
8. If the document is unclear or the scheme is inconsistent, flag it.

This is a preliminary assessment, not a final teacher-approved result.

OUTPUT FORMAT:
Return valid JSON only. Do not include Markdown code fences or
any introductory or concluding text.


Use this structure:
{{
  "question1": {{
    "Marks": 1,
    "reasoning": "Explanation for the awarded marks.",
    "maximum_marks": 1,
    "review_required": false
  }},
  "question2": {{
    "Marks": 0.5,
    "reasoning": "Partially correct answer; partial credit awarded.",
    "maximum_marks": 2,
    "review_required": false
  }}
}}


RULES:
1. Include every question and sub-question found in the paper.
2. "Marks" must be a number, not a string.
3. "reasoning" must explain why the marks were awarded.
4. "maximum_marks" must match the official marking scheme.
5. Set "review_required" to true if handwriting is unclear,
   pages or answers are missing, or teacher markings conflict
   with the AI assessment.
6. Do not invent answers for missing or unreadable questions.
7. Award partial marks only when justified by the marking scheme.
8. Ensure the output is valid JSON with no trailing commas.
"""
for attempt in range(3):
    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[uploaded_pdf, prompt]
        )
        break
    except Exception:
        if attempt == 2:
            raise
        print("Gemini is busy. Retrying in 5 seconds...")
        time.sleep(5)
    model="gemini-3.8-flash",
    contents=[uploaded_pdf, prompt]

# Save Gemini's evaluation
results_folder = BASE / "Results"
results_folder.mkdir(exist_ok=True)

result_text = response.text or "No evaluation text returned."

output_file = results_folder / f"{pdf_path.stem}_evaluation.txt"
output_file.write_text(result_text, encoding="utf-8")

print("\n===== GEMINI EVALUATION =====\n")
print(result_text)

print(f"\nEvaluation saved to: {output_file}")