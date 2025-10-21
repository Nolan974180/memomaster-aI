# === MemoMaster (Gradio + Floating Chat) ===
# Génère des fiches de révision (PDF) + bulle de chat IA flottante (mobile-friendly)

import os, io, traceback
import gradio as gr
from openai import OpenAI

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# === Config ===
FREE_LIMIT = 5
DEFAULT_MODEL = "gpt-4o-mini"

# === OpenAI client (clé via variable d'env OPENAI_API_KEY) ===
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# --- Utilitaires ---
def export_to_pdf(text: str, filename: str = "fiche_revision.pdf"):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    flow = [Paragraph(p, styles["Normal"]) for p in text.split("\n") if p.strip()]
    doc.build(flow)
    with open(filename, "wb") as f:
        f.write(buf.getvalue())
    return filename

def summarize_file(file, cours_titre):
    # Lecture simple (txt/pdf/docx déjà gérés côté rendu de texte par l’utilisateur)
    content = ""
    try:
        content = file.read().decode("utf-8", errors="ignore")
    except Exception:
        content = "Impossible de lire le fichier (essayez .txt pour le test)."

    try:
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system",
                 "content": "Tu es un assistant qui crée des fiches de révision claires et structurées (titres, puces, formules en texte)."},
                {"role": "user",
                 "content": f"Crée une fiche de révision claire et concise pour le cours « {cours_titre} » à partir de :\n\n{content}"}
            ],
            temperature=0.4
        )
        summary = resp.choices[0].message.content.strip()
        pdf_path = export_to_pdf(summary)
        return summary, pdf_path
    except Exception as e:
        traceback.print_exc()
        return f"Erreur : {e}", None

# --- Chat IA (bulle) ---
def chat_step(history, user_msg):
    if not user_msg or not user_msg.strip():
        return history, ""

    history = history + [[user_msg, "…"]]

    try:
        # Construit l'historique au format OpenAI
        messages = [{"role": "system", "content": "Tu es un tuteur bienveillant qui aide les étudiants à réviser."}]
        for u, a in history[:-1]:
            messages.append({"role": "user", "content": u})
            messages.append({"role": "assistant", "content": a})

        messages.append({"role": "user", "content": user_msg})

        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.5,
        )
        answer = resp.choices[0].message.content.strip()
        history[-1][1] = answer
    except Exception as e:
        history[-1][1] = f"Erreur : {e}"

    return history, ""

# === UI ===
with gr.Blocks(theme=gr.themes.Soft(), css="""
/* Cacher le footer Gradio */
footer { display: none !important; }

/* Bulle flottante */
#chat-fab {
  position: fixed; right: 16px; bottom: 16px; z-index: 9999;
  width: 58px; height: 58px; border-radius: 50%;
  background: #ff6b2c; color: white; border: none;
  box-shadow: 0 8px 20px rgba(0,0,0,.2);
  font-size: 26px; line-height: 58px; text-align: center;
}

/* Panneau de chat */
#chat-panel {
  position: fixed; right: 12px; bottom: 86px; z-index: 9998;
  width: min(380px, 92vw); height: 64vh; max-height: 560px;
  background: #111; border: 1px solid #333; border-radius: 14px;
  display: none; flex-direction: column; overflow: hidden;
  box-shadow: 0 20px 48px rgba(0,0,0,.35);
}

/* Entête chat */
#chat-header {
  display:flex; align-items:center; justify-content:space-between;
  padding: 10px 14px; background:#1a1a1a; border-bottom:1px solid #2c2c2c;
}
#chat-header h4 { margin:0; font-size: 15px; }
#chat-close {
  background: transparent; color: #bbb; border: none; font-size: 20px;
}

/* Corps chat */
#chat-body { padding: 10px; height: 100%; overflow: auto; }

/* Mobile : légèrement plus grand bouton */
@media (max-width: 480px) {
  #chat-fab { width: 64px; height: 64px; font-size: 28px; line-height: 64px; }
}
""") as demo:

    gr.HTML("""
    <h1>🧠 MémoMaster - Générateur de fiches IA</h1>
    <p>Générez automatiquement des fiches de révision à partir de vos cours (.pdf/.docx/.txt). Palier gratuit : 5 cours par session.</p>
    """)
    # Formulaire principale
    with gr.Group():
        with gr.Row():
            file_in = gr.File(label="Téléverser un fichier (.txt, .pdf, .docx)")
        title_in = gr.Textbox(label="Titre du cours", placeholder="Ex: Chapitre 3 – Thermodynamique")
        with gr.Row():
            btn = gr.Button("Générer", variant="primary")
            clear_btn = gr.ClearButton([file_in, title_in])

    with gr.Row():
        summary_out = gr.Textbox(label="Fiche de révision générée", lines=16)
    pdf_out = gr.File(label="Télécharger le PDF")

    # État : compteur gratuit (démo basique)
    counter = gr.State(0)

    # --- Bulle + Panneau Chat ---
    gr.HTML("""
    <button id="chat-fab">💬</button>
    <div id="chat-panel">
      <div id="chat-header">
        <h4>Chat d’aide</h4>
        <button id="chat-close">✕</button>
      </div>
      <div id="chat-body"></div>
    </div>
    <script>
      const fab = document.getElementById("chat-fab");
      const panel = document.getElementById("chat-panel");
      const closeBtn = document.getElementById("chat-close");
      fab.onclick = () => panel.style.display = (panel.style.display === "flex" ? "none" : "flex");
      closeBtn.onclick = () => panel.style.display = "none";
    </script>
    """)  # Le contenu du chatbot réel est ci-dessous (via composants Gradio)

    # On crée le vrai chatbot (caché visuellement, on le monte dans le panel via JS)
    with gr.Column(visible=True) as hidden_chat:
        chat = gr.Chatbot(height=360, label=None)
        chat_state = gr.State([])
        chat_in = gr.Textbox(placeholder="Pose ta question…", lines=1)
        with gr.Row():
            chat_send = gr.Button("Envoyer", variant="primary")
            chat_clear = gr.Button("Effacer")

    # Lier événements
    def controller(file, title, count):
        # palier gratuit
        if count is None:
            count = 0
        if count >= FREE_LIMIT:
            msg = (f"⛔ Palier gratuit atteint ({FREE_LIMIT}). "
                   f"Pense à passer au plan premium pour continuer.")
            return msg, None, count
        summary, pdf = summarize_file(file, title)
        count += 1
        return summary, pdf, count

    btn.click(
        controller,
        inputs=[file_in, title_in, counter],
        outputs=[summary_out, pdf_out, counter]
    )

    # Chat
    def _chat_submit(history, user_msg):
        return chat_step(history, user_msg)

    chat_send.click(_chat_submit, [chat_state, chat_in], [chat_state, chat_in, chat], queue=False)
    chat_in.submit(_chat_submit, [chat_state, chat_in], [chat_state, chat_in, chat], queue=False)
    chat_clear.click(lambda: ([], ""), None, [chat, chat_in], queue=False)

# === Lancement Render ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    demo.launch(server_name="0.0.0.0", server_port=port, show_error=True)
