# === MemoMaster (Gradio UI) ===
# Génère des fiches de révision IA à partir de fichiers (.pdf, .docx, .txt)

import os, io, traceback
import gradio as gr
from openai import OpenAI

# PDF export
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# Lecture DOCX / PDF
from docx import Document as DocxDocument      # package: python-docx
from pdfminer.high_level import extract_text    # package: pdfminer.six

# === Config ===
DEFAULT_MODEL = "gpt-4o-mini"

# === OpenAI Client (clé lue dans les variables d'env de Render) ===
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# === Utils: convertir un input Gradio File -> texte ===
def _read_uploaded_file(file_obj) -> str:
    """
    Supporte :
      - gradio qui renvoie un dict ({"name": <path>, ...})
      - gradio qui renvoie un chemin (str) ou un fichier temporaire (obj avec .name)
    """
    # Normaliser vers un chemin
    path = None
    if file_obj is None:
        return ""
    if isinstance(file_obj, dict) and "name" in file_obj:
        path = file_obj["name"]
    elif isinstance(file_obj, str):
        path = file_obj
    elif hasattr(file_obj, "name"):
        path = file_obj.name

    if not path or not os.path.exists(path):
        return ""

    lower = path.lower()
    try:
        if lower.endswith(".txt"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif lower.endswith(".docx"):
            doc = DocxDocument(path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif lower.endswith(".pdf"):
            return extract_text(path) or ""
        else:
            # Fallback lecture binaire → utf-8
            with open(path, "rb") as f:
                return f.read().decode("utf-8", errors="ignore")
    except Exception:
        traceback.print_exc()
        return ""

# === PDF Export ===
def export_to_pdf(text, filename="fiche_revision.pdf"):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    flow = [Paragraph(p, styles["Normal"]) for p in text.split("\n") if p.strip()]
    doc.build(flow)
    with open(filename, "wb") as f:
        f.write(buf.getvalue())
    return filename

# === IA Summary Function ===
def generate_summary(file, cours_titre):
    source = _read_uploaded_file(file)
    if not source.strip():
        return "❌ Fichier vide ou illisible. Essaie .txt, .pdf ou .docx.", None

    try:
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system",
                 "content": "Tu es un assistant qui génère des fiches de révision claires, structurées et synthétiques (titres, puces, exemples)."},
                {"role": "user",
                 "content": f"Crée une fiche de révision claire et concise pour le cours « {cours_titre} » à partir de ce contenu :\n\n{source}"}
            ],
            temperature=0.4
        )
        summary = resp.choices[0].message.content
        pdf_path = export_to_pdf(summary)
        return summary, pdf_path
    except Exception as e:
        traceback.print_exc()
        return f"Erreur : {str(e)}", None

# === Gradio UI ===
iface = gr.Interface(
    fn=generate_summary,
    inputs=[
        gr.File(label="Téléverser un fichier (.txt, .pdf, .docx)"),
        gr.Textbox(label="Titre du cours", placeholder="Ex: Chapitre 3 – Thermodynamique")
    ],
    outputs=[
        gr.Textbox(label="Fiche de révision générée", lines=18),
        gr.File(label="Télécharger le PDF")
    ],
    title="🧠 MémoMaster - Générateur de fiches IA",
    description="Générez automatiquement des fiches de révision à partir de vos cours (.pdf/.docx/.txt).",
)

# === Lancement Render / Local ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))  # Render injecte PORT
    iface.launch(server_name="0.0.0.0", server_port=port, share=False)