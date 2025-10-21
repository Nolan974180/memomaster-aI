# === MémoMaster (Render + Gradio) ============================================
# - Onglet 1 : générateur de fiches IA à partir de .txt / .pdf / .docx (+ export PDF)
# - Onglet 2 : bulle de chat (tuteur IA)
# - Branding Gradio masqué
# - Lit la clé depuis la variable d'env OPENAI_API_KEY
# ============================================================================

import os, io, tempfile, traceback

import gradio as gr
from openai import OpenAI

# --- Extraction texte depuis .pdf / .docx / .txt ---
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document

# --- Export PDF ---
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# === Config ===
DEFAULT_MODEL = "gpt-4o-mini"   # peu coûteux, assez bon pour ce cas
SYSTEM_SUMMARY = (
    "Tu es un assistant qui produit des fiches de révision claires, structurées, "
    "avec titres, sous-titres, définitions, exemples, rappels de méthode et, si utile, "
    "quelques QCM ou Vrai/Faux en fin de fiche."
)
SYSTEM_TUTOR = (
    "Tu es un tuteur bienveillant. Explique simplement, propose des exemples, des quiz, "
    "et reformule si on te le demande. Si l’utilisateur colle un cours/exercice, aide-le à réviser."
)

# === OpenAI client (clé en variable d'environnement) ===
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# === Outils ==================================================================

def read_file_to_text(upfile) -> str:
    """Retourne le texte du fichier (.txt/.pdf/.docx)."""
    if upfile is None:
        return ""
    name = (getattr(upfile, "name", "") or "").lower()

    try:
        if name.endswith(".pdf"):
            return pdf_extract_text(upfile.name)
        elif name.endswith(".docx"):
            doc = Document(upfile.name)
            return "\n".join(p.text for p in doc.paragraphs)
        else:
            # .txt ou inconnu -> on tente UTF-8
            with open(upfile.name, "rb") as f:
                return f.read().decode("utf-8", errors="ignore")
    except Exception:
        return "⚠️ Erreur pendant la lecture du fichier."

def export_to_pdf(text: str) -> str:
    """Crée un PDF temporaire avec le texte et renvoie le chemin du fichier."""
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    # fichier temporaire (Render/Gradio ok)
    fd, path = tempfile.mkstemp(prefix="fiche_", suffix=".pdf")
    os.close(fd)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    flow = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            flow.append(Spacer(1, 8))
        else:
            flow.append(Paragraph(line, normal))
    doc.build(flow)

    with open(path, "wb") as f:
        f.write(buf.getvalue())
    return path

# === IA : génération de fiche ===============================================

def generate_summary(upfile, cours_titre):
    try:
        content = read_file_to_text(upfile)
        if not content.strip():
            return "⚠️ Aucun texte détecté dans le fichier.", None

        user_prompt = (
            f"Crée une fiche de révision claire et concise pour le cours « {cours_titre or 'Sans titre'} ».\n\n"
            f"--- CONTENU DU COURS ---\n{content}\n"
            f"------------------------\n"
            "Structure attendue :\n"
            "1) Titre / Objectifs\n2) Notions clés (définitions courtes)\n"
            "3) Méthodes / étapes\n4) Exemples\n5) Erreurs fréquentes\n6) Mini-quiz (3-5 QCM ou V/F)\n"
        )

        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_SUMMARY},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=1200,
        )
        summary = resp.choices[0].message.content
        pdf_path = export_to_pdf(summary)
        return summary, pdf_path

    except Exception as e:
        return f"❌ Erreur : {e}", None

# === IA : bulle de chat (tuteur) ============================================

def tutor_chat(message, history):
    """
    history: liste [(user_msg, assistant_msg), ...]
    retourne la réponse assistant (str)
    """
    try:
        msgs = [{"role": "system", "content": SYSTEM_TUTOR}]

        # Reconstituer le contexte
        for user_msg, assistant_msg in history:
            if user_msg:
                msgs.append({"role": "user", "content": user_msg})
            if assistant_msg:
                msgs.append({"role": "assistant", "content": assistant_msg})

        msgs.append({"role": "user", "content": message})

        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=msgs,
            temperature=0.3,
            max_tokens=700,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"❌ Erreur : {e}"

# === UI Gradio ===============================================================

CUSTOM_CSS = """
footer {display:none !important;}
.svelte-1ipelgc {display:none !important;}
"""

with gr.Blocks(css=CUSTOM_CSS, theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🧠 MémoMaster")

    with gr.Tab("📝 Générateur de fiches"):
        gen = gr.Interface(
            fn=generate_summary,
            inputs=[
                gr.File(label="Téléverser un fichier (.txt, .pdf, .docx)"),
                gr.Textbox(label="Titre du cours", placeholder="Ex: Chapitre 3 – Thermodynamique"),
            ],
            outputs=[
                gr.Textbox(label="Fiche de révision générée"),
                gr.File(label="⬇️ Télécharger le PDF"),
            ],
            title="Générateur de fiches IA",
            description="Téléverse ton cours, donne un titre, puis clique Submit.",
            allow_flagging="never",
        )
        gen.render()

    with gr.Tab("💬 Chat IA"):
        gr.ChatInterface(
            fn=tutor_chat,
            title="Bulle de chat — Tuteur IA",
            description="Pose tes questions, demande des explications, des quiz, des résumés…",
            retry_btn="Reformuler",
            undo_btn="Annuler la dernière",
            clear_btn="Nouvelle discussion",
            textbox=gr.Textbox(placeholder="Écris ici… (Entrée pour envoyer)"),
        )

# === Lancement pour Render ===================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.launch(server_name="0.0.0.0", server_port=port, share=False)