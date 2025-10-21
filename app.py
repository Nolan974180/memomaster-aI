# === MémoMaster (Gradio + Chat IA) ===
# Génère des fiches de révision à partir de fichiers (.txt/.pdf/.docx)
# + Bulle de chat IA intégrée (compatible Gradio 4.44)

import os, io, traceback
import gradio as gr
from openai import OpenAI
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from pdfminer.high_level import extract_text
from docx import Document

# === Config ===
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"

# === Lecture des fichiers ===
def lire_fichier(file):
    if file is None:
        return ""
    name = file.name.lower()
    try:
        if name.endswith(".txt"):
            return file.read().decode("utf-8", errors="ignore")
        if name.endswith(".pdf"):
            return extract_text(file.name)
        if name.endswith(".docx"):
            doc = Document(file.name)
            return "\n".join(p.text for p in doc.paragraphs)
        return file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"Erreur de lecture : {e}"

# === Export PDF ===
def export_pdf(text, filename="fiche_revision.pdf"):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    flow = [Paragraph(p, styles["Normal"]) for p in text.split("\n") if p.strip()]
    doc.build(flow)
    with open(filename, "wb") as f:
        f.write(buf.getvalue())
    return filename

# === Génération IA ===
def generer_fiche(file, titre):
    contenu = lire_fichier(file)
    if not contenu.strip():
        return "⚠️ Fichier vide ou illisible.", None

    try:
        prompt = (
            f"Crée une fiche de révision claire et concise pour le cours '{titre}'. "
            "Structure la fiche avec : définitions, formules, points clés, erreurs fréquentes, résumé synthétique.\n\n"
            f"Contenu du cours :\n{contenu[:12000]}"
        )
        rep = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Tu es un assistant d'étude clair et pédagogue."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        fiche = rep.choices[0].message.content
        pdf = export_pdf(fiche)
        return fiche, pdf
    except Exception as e:
        traceback.print_exc()
        return f"❌ Erreur : {e}", None

# === Chat IA ===
def repondre_chat(history, message):
    if not message.strip():
        return history
    try:
        messages = [{"role": "system", "content": "Tu aides l'étudiant à comprendre ses cours."}]
        for user, bot in history:
            if user:
                messages.append({"role": "user", "content": user})
            if bot:
                messages.append({"role": "assistant", "content": bot})
        messages.append({"role": "user", "content": message})

        rep = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.4)
        bot_reply = rep.choices[0].message.content
        history.append((message, bot_reply))
        return history
    except Exception as e:
        history.append((message, f"❌ Erreur IA : {e}"))
        return history

# === Interface Gradio ===
with gr.Blocks(css="""
/* Bulle de chat flottante */
#bubble {
  position: fixed; right: 18px; bottom: 18px;
  background: #ff6d00; color: white;
  font-size: 28px; border-radius: 50%; border: none;
  width: 56px; height: 56px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 10px rgba(0,0,0,.3);
  cursor: pointer; z-index: 9999;
}
#chatbox {
  display: none; position: fixed;
  right: 18px; bottom: 80px;
  width: 340px; max-height: 70vh;
  background: #1e1e1e; border-radius: 10px;
  box-shadow: 0 5px 20px rgba(0,0,0,.4);
  overflow: hidden; z-index: 9999;
}
""") as app:

    gr.Markdown("## 🧠 MémoMaster — Générateur de fiches IA")
    gr.Markdown(
        "Téléversez un fichier (.txt, .pdf, .docx) puis générez automatiquement une fiche de révision. "
        "Utilisez la bulle 💬 pour discuter avec l'IA."
    )

    with gr.Row():
        fichier = gr.File(label="Fichier du cours (.txt/.pdf/.docx)")
        titre = gr.Textbox(label="Titre du cours", placeholder="Ex: Chapitre 3 – Thermodynamique")

    bouton = gr.Button("Générer la fiche")
    sortie_txt = gr.Textbox(label="Fiche générée", lines=20)
    sortie_pdf = gr.File(label="Télécharger le PDF")

    bouton.click(generer_fiche, [fichier, titre], [sortie_txt, sortie_pdf])

    # Chat flottant
    gr.HTML(
        '<button id="bubble">💬</button>'
        '<div id="chatbox">'
        '  <div style="background:#333;padding:10px;color:#fff;">Chat IA — MémoMaster</div>'
        '  <div id="chat-content"></div>'
        '</div>'
    )

    with gr.Column(elem_id="chat-content"):
        chatbot = gr.Chatbot(height=360)
        user_input = gr.Textbox(placeholder="Écris ici…", label="Message")
        clear_btn = gr.ClearButton([chatbot, user_input])

        user_input.submit(repondre_chat, [chatbot, user_input], chatbot).then(
            lambda: "", None, user_input
        )

    app.load(
        None, None, None, _js="""
() => {
  const bubble = document.getElementById('bubble');
  const chatbox = document.getElementById('chatbox');
  if (bubble && chatbox) {
    bubble.onclick = () => {
      chatbox.style.display = chatbox.style.display === 'block' ? 'none' : 'block';
    };
  }
}
"""
    )

# === Lancement ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.launch(server_name="0.0.0.0", server_port=port)
