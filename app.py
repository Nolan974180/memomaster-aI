# === MemoMaster (Gradio UI) ===
# Permet de générer des fiches de révision IA à partir de fichiers (.txt, .docx, .pdf)
# Palier gratuit : 5 cours par session

import os, io, time, traceback
import gradio as gr
from openai import OpenAI

# === Config ===
FREE_LIMIT = 5  # nombre de cours gratuits
DEFAULT_MODEL = "gpt-4o-mini"

# === PDF export ===
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def export_to_pdf(text, filename="fiche_revision.pdf"):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    flow = [Paragraph(p, styles["Normal"]) for p in text.split("\n\n")]
    doc.build(flow)
    with open(filename, "wb") as f:
        f.write(buf.getvalue())
    return filename

# === Lecture de fichiers ===
def read_files(files):
    text = ""
    if not files: return text
    for file in files:
        with open(file.name, "r", encoding="utf-8", errors="ignore") as f:
            text += f.read() + "\n\n"
    return text

# === Génération principale ===
def generate_sheet(language, model, text, include_quiz, files, counter):
    if counter is None: counter = 0
    if counter >= FREE_LIMIT:
        return f"🚫 Palier gratuit atteint ({FREE_LIMIT} cours). Passe au plan payant pour continuer.", None, None, counter

    # Lecture du contenu
    text_from_files = read_files(files)
    source = (text or "").strip()
    if text_from_files.strip():
        source += "\n\n" + text_from_files
    if len(source) < 20:
        return "❌ Ajoute un texte plus long ou un fichier (.txt, .pdf, .docx).", None, None, counter

    # Requête OpenAI
    try:
        client = OpenAI()
        prompt = f"Génère une fiche de révision en {language}. Inclure quiz : {include_quiz}. Contenu :\n{source[:5000]}"
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        content = resp.choices[0].message.content.strip()

        # Export fichiers
        txt_file = "fiche_revision.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(content)
        pdf_file = export_to_pdf(content)

        counter += 1
        return content, txt_file, pdf_file, counter

    except Exception as e:
        traceback.print_exc()
        return f"⚠️ Erreur : {str(e)}", None, None, counter

# === Interface Gradio ===
def launch_app():
    with gr.Blocks(title="MemoMaster — Fiches de révision IA (FR/EN)") as demo:
        gr.Markdown("""
        ## 🧠 MemoMaster — Fiches de révision IA (FR/EN)
        Colle ton cours **ou importe des fichiers (.txt, .docx, .pdf)**, choisis la langue, puis clique **Générer**.  
        *Palier gratuit : 5 cours par session. La clé API est cachée côté serveur.*
        """)

        language = gr.Dropdown(["fr", "en"], value="fr", label="Lang / Langue")
        model = gr.Dropdown(["gpt-4o-mini", "gpt-3.5-turbo"], value=DEFAULT_MODEL, label="Modèle")
        text = gr.Textbox(lines=8, label="Texte (optionnel si tu importes des fichiers)")
        files = gr.Files(label="📂 Importer des fichiers", type="filepath")
        include_quiz = gr.Checkbox(value=True, label="Inclure un quiz de révision ?")
        btn = gr.Button("🚀 Générer la fiche de révision")

        out_md = gr.Markdown()
        out_txt = gr.File(label="📄 Télécharger .txt")
        out_pdf = gr.File(label="🖨️ Télécharger .pdf")
        counter = gr.State(0)

        btn.click(
            fn=generate_sheet,
            inputs=[language, model, text, include_quiz, files, counter],
            outputs=[out_md, out_txt, out_pdf, counter],
        )

    demo.launch(share=False)

if __name__ == "__main__":
    launch_app()
