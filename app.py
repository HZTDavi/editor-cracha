"""
App web local (Streamlit) pro editor de crachá.

Rodar:
    streamlit run app.py

Abre em http://localhost:8501 no navegador.
"""

import cv2
import numpy as np
import streamlit as st

import editor_cracha as ec

st.set_page_config(page_title="Editor de Crachá", page_icon="🪪", layout="centered")
st.title("🪪 Editor de Crachá")
st.caption(
    "Envie a imagem do crachá. O app tenta achar os textos automaticamente (OCR); "
    "edite o que quiser trocar e gere a imagem final mantendo o resto intocado."
)

uploaded = st.file_uploader("Imagem do crachá", type=["png", "jpg", "jpeg", "bmp", "webp"])

if uploaded is None:
    st.info("Envie uma imagem pra começar.")
    st.stop()

file_bytes = np.frombuffer(uploaded.getvalue(), np.uint8)
image_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

if image_bgr is None:
    st.error("Não consegui ler essa imagem.")
    st.stop()

# roda o OCR só quando troca de imagem (evita reprocessar a cada interação)
if st.session_state.get("uploaded_name") != uploaded.name:
    with st.spinner("Procurando textos na imagem..."):
        st.session_state.lines = ec.ocr_lines(image_bgr, lang="por+eng")
    st.session_state.uploaded_name = uploaded.name
    st.session_state.pop("result", None)

lines = st.session_state.lines

preview = image_bgr.copy()
for i, line in enumerate(lines):
    x1, y1, x2, y2 = line["bbox"]
    cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 0, 255), 2)
    cv2.putText(preview, str(i + 1), (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

st.image(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB), caption="Textos detectados automaticamente", use_container_width=True)

if not lines:
    st.warning("Nenhum texto foi detectado automaticamente. Use a área manual abaixo.")

st.subheader("Textos detectados — edite o que quiser trocar")
edits = {}
for i, line in enumerate(lines):
    edits[i] = st.text_input(f"{i + 1}. \"{line['text']}\"", value=line["text"], key=f"line_{i}")

with st.expander("Área manual (pra texto que o OCR não achou)"):
    st.caption("Informe as coordenadas em pixels do canto superior-esquerdo e inferior-direito do texto.")
    h, w = image_bgr.shape[:2]
    c1, c2, c3, c4 = st.columns(4)
    mx1 = c1.number_input("x1", 0, w, 0)
    my1 = c2.number_input("y1", 0, h, 0)
    mx2 = c3.number_input("x2", 0, w, 0)
    my2 = c4.number_input("y2", 0, h, 0)
    manual_text = st.text_input("Texto novo para essa área", key="manual_text")
    add_manual = st.checkbox("Aplicar essa área manual também")

force_bold_label = st.radio("Peso da fonte no texto novo", ["Automático", "Negrito", "Normal"], horizontal=True)
force_bold = {"Automático": None, "Negrito": True, "Normal": False}[force_bold_label]

if st.button("Gerar crachá", type="primary"):
    result = image_bgr.copy()
    applied = 0
    for i, line in enumerate(lines):
        new_text = edits[i].strip()
        if new_text and new_text != line["text"]:
            result = ec.apply_at_bbox(result, line["bbox"], new_text, force_bold=force_bold)
            applied += 1
    if add_manual and manual_text.strip() and mx2 > mx1 and my2 > my1:
        result = ec.apply_at_bbox(result, (int(mx1), int(my1), int(mx2), int(my2)), manual_text.strip(), force_bold=force_bold)
        applied += 1

    if applied == 0:
        st.info("Nenhuma alteração pra aplicar — edite algum texto acima ou marque a área manual.")
    else:
        st.session_state.result = result
        st.success(f"{applied} texto(s) alterado(s).")

if "result" in st.session_state:
    st.subheader("Resultado")
    st.image(cv2.cvtColor(st.session_state.result, cv2.COLOR_BGR2RGB), use_container_width=True)
    ok, buf = cv2.imencode(".png", st.session_state.result)
    st.download_button("Baixar imagem", data=buf.tobytes(), file_name="cracha_editado.png", mime="image/png")
