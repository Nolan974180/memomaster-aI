# === MemoMaster (Gradio UI) ===
# Permet de générer des fiches de révision IA à partir de fichiers (.pdf, .docx, .txt)
# Palier gratuit : 5 cours par session

import os, io, time, traceback
import gradio as gr
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# === Config ===
FREE_LIMIT = 5
DEFAULT_MODEL = "gpt-4o-mini"

# === OpenAI Client (utilise la clé depuis Render) ===
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    try:
        content = file.read().decode("utf-8", errors="ignore")
    except Exception:
        content = "Erreur de lecture du fichier."

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "Tu es un assistant qui génère des fiches de révision claires et structurées."},
                {"role": "user", "content": f"Crée une fiche de révision claire et concise pour le cours '{cours_titre}':\n\n{content}"}
            ],
            temperature=0.4
        )
        summary = response.choices[0].message.content
        filename = export_to_pdf(summary)
        return summary, filename
    except Exception as e:
        return f"Erreur : {str(e)}", None

# === Gradio UI ===
iface = gr.Interface(
    fn=generate_summary,
    inputs=[
        gr.File(label="Téléverser un fichier (.txt, .pdf, .docx)"),
        gr.Textbox(label="Titre du cours")
    ],
    outputs=[
        gr.Textbox(label="Fiche de révision générée"),
        gr.File(label="Télécharger le PDF")
    ],
    title="🧠 MémoMaster - Générateur de fiches IA",
    description="Générez automatiquement des fiches de révision à partir de vos cours. (Palier gratuit : 5 cours par session)"
)

# === Lancement Render ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    iface.launch(server_name="0.0.0.0", server_port=port, share=False)