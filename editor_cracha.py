#!/usr/bin/env python3
"""
Editor de crachas: troca textos (nome, data, cargo, etc.) em uma imagem
de crachá mantendo o resto (fundo, foto, layout) intocado.

Fluxo:
  1. Tenta achar o texto antigo automaticamente via OCR (Tesseract).
  2. Mostra a área encontrada e pede confirmação.
  3. Se não achar ou você recusar, abre uma janela para você marcar
     manualmente a área com o mouse.
  4. Remove o texto antigo (inpainting, preservando o fundo real) e
     escreve o texto novo tentando casar cor/tamanho/peso da fonte original.

Uso:
  # troca pontual, com confirmação automática
  python3 editor_cracha.py cracha.png --replace "JOAO SILVA=MARIA SOUZA" -o saida.png

  # várias trocas na mesma imagem (nome + data, por exemplo)
  python3 editor_cracha.py cracha.png \
      --replace "JOAO SILVA=MARIA SOUZA" \
      --replace "01/01/2024=15/03/2026" \
      -o saida.png

  # modo totalmente manual/interativo (sem OCR), vai perguntando o que trocar
  python3 editor_cracha.py cracha.png -o saida.png --manual
"""

import argparse
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import pytesseract
    from pytesseract import Output
except ImportError:
    pytesseract = None

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

FONT_REGULAR = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"


# --------------------------------------------------------------------------
# OCR: localizar o texto antigo automaticamente
# --------------------------------------------------------------------------

def ocr_lines(image_bgr, lang="por+eng"):
    """Roda o OCR e agrupa as palavras detectadas em linhas, com bbox."""
    if pytesseract is None:
        return []

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    data = pytesseract.image_to_data(rgb, lang=lang, output_type=Output.DICT)

    lines = {}
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        conf = float(data["conf"][i]) if data["conf"][i] not in ("-1", -1) else -1
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        line = lines.setdefault(key, {"words": [], "boxes": []})
        line["words"].append(text)
        line["boxes"].append((x, y, x + w, y + h))
        if conf >= 0:
            line.setdefault("confs", []).append(conf)

    result = []
    for line in lines.values():
        xs1 = [b[0] for b in line["boxes"]]
        ys1 = [b[1] for b in line["boxes"]]
        xs2 = [b[2] for b in line["boxes"]]
        ys2 = [b[3] for b in line["boxes"]]
        bbox = (min(xs1), min(ys1), max(xs2), max(ys2))
        text = " ".join(line["words"])
        confs = line.get("confs", [])
        avg_conf = sum(confs) / len(confs) if confs else 0
        result.append({"text": text, "bbox": bbox, "conf": avg_conf})
    return result


def find_best_match(lines, target_text):
    """Acha a linha do OCR mais parecida com o texto que queremos trocar."""
    if not lines:
        return None
    if fuzz is not None:
        scored = [(fuzz.token_sort_ratio(target_text.upper(), l["text"].upper()), l) for l in lines]
    else:
        # fallback simples sem rapidfuzz: comparação exata/substring
        def score(a, b):
            a, b = a.upper(), b.upper()
            if a == b:
                return 100
            if a in b or b in a:
                return 80
            return 0
        scored = [(score(target_text, l["text"]), l) for l in lines]

    scored.sort(key=lambda t: t[0], reverse=True)
    best_score, best_line = scored[0]
    return best_score, best_line


# --------------------------------------------------------------------------
# Confirmação / seleção manual
# --------------------------------------------------------------------------

def show_preview_and_confirm(image_bgr, bbox, label):
    x1, y1, x2, y2 = bbox
    preview = image_bgr.copy()
    cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 0, 255), 2)

    fd, path = tempfile.mkstemp(suffix=".png", prefix="preview_")
    os.close(fd)
    cv2.imwrite(path, preview)

    print(f"\n[OCR] Candidato para \"{label}\": bbox={bbox}")
    print(f"[OCR] Prévia salva em: {path}")
    for opener in ("xdg-open", "open"):
        try:
            subprocess.Popen([opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            break
        except FileNotFoundError:
            continue

    resp = input("Essa é a área certa? [S/n] ").strip().lower()
    return resp in ("", "s", "sim", "y", "yes")


def manual_select(image_bgr, label):
    print(f"\nSelecione manualmente a área de \"{label}\" na janela que abriu.")
    print("Arraste o retângulo com o mouse, depois ENTER/SPACE para confirmar (ESC cancela).")
    window = f"Selecionar: {label}"
    x, y, w, h = cv2.selectROI(window, image_bgr, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(window)
    if w == 0 or h == 0:
        return None
    return (x, y, x + w, y + h)


# --------------------------------------------------------------------------
# Estimativa de estilo (cor / tamanho / peso) e remoção do texto antigo
# --------------------------------------------------------------------------

def estimate_style_and_mask(image_bgr, bbox, pad=3):
    x1, y1, x2, y2 = bbox
    h_img, w_img = image_bgr.shape[:2]
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w_img, x2 + pad)
    y2 = min(h_img, y2 + pad)
    crop = image_bgr[y1:y2, x1:x2]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # borda do recorte ~ cor de fundo; usamos pra decidir se o texto é
    # mais claro ou mais escuro que o fundo
    border_pixels = np.concatenate([
        gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]
    ])
    bg_level = float(np.median(border_pixels))

    _, mask_dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, mask_light = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # escolhe a máscara cujos pixels "de texto" mais se afastam do fundo
    def contrast_score(mask):
        sel = gray[mask > 0]
        if sel.size == 0:
            return -1
        return abs(float(np.mean(sel)) - bg_level)

    mask = mask_dark if contrast_score(mask_dark) >= contrast_score(mask_light) else mask_light

    text_ratio = float(np.count_nonzero(mask)) / mask.size
    if text_ratio > 0.6:
        # threshold pegou o fundo inteiro em vez do texto: inverte
        mask = cv2.bitwise_not(mask)
        text_ratio = 1 - text_ratio

    text_pixels = crop[mask > 0]
    if text_pixels.size == 0:
        color_bgr = (0, 0, 0)
    else:
        color_bgr = tuple(int(v) for v in np.median(text_pixels.reshape(-1, 3), axis=0))

    bold = text_ratio > 0.28  # heurística: texto "denso" -> provavelmente negrito

    return {
        "crop_box": (x1, y1, x2, y2),
        "mask": mask,
        "color_bgr": color_bgr,
        "bold": bold,
        "box_height": y2 - y1,
    }


def remove_text(image_bgr, style):
    x1, y1, x2, y2 = style["crop_box"]
    crop = image_bgr[y1:y2, x1:x2]
    mask = cv2.dilate(style["mask"], np.ones((3, 3), np.uint8), iterations=1)
    inpainted = cv2.inpaint(crop, mask, 3, cv2.INPAINT_TELEA)
    out = image_bgr.copy()
    out[y1:y2, x1:x2] = inpainted
    return out


# --------------------------------------------------------------------------
# Escrever o texto novo
# --------------------------------------------------------------------------

def fit_font(draw, text, box_w, box_h, bold, min_size=8, max_size=200, font_path=None):
    if font_path is None:
        font_path = FONT_BOLD if bold else FONT_REGULAR
    size = min(max_size, max(min_size, int(box_h * 0.85)))
    while size > min_size:
        font = ImageFont.truetype(font_path, size)
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        if (r - l) <= box_w * 1.05 and (b - t) <= box_h * 1.15:
            return font
        size -= 1
    return ImageFont.truetype(font_path, min_size)


def draw_new_text(image_bgr, bbox, text, color_bgr, bold, font_path=None):
    x1, y1, x2, y2 = bbox
    box_w, box_h = x2 - x1, y2 - y1

    pil_img = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    font = fit_font(draw, text, box_w, box_h, bold, font_path=font_path)
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = r - l, b - t

    draw_x = x1
    draw_y = y1 + (box_h - text_h) / 2 - t

    color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0])
    draw.text((draw_x, draw_y), text, font=font, fill=color_rgb)

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


# --------------------------------------------------------------------------
# Orquestração de uma troca (old_text -> new_text)
# --------------------------------------------------------------------------

def apply_at_bbox(image_bgr, bbox, new_text, force_bold=None, font_override=None):
    """Aplica a troca num bbox já conhecido (sem OCR nem seleção manual). Usado pelo CLI e pelo app web."""
    style = estimate_style_and_mask(image_bgr, bbox)
    cleaned = remove_text(image_bgr, style)
    bold = style["bold"] if force_bold is None else force_bold
    return draw_new_text(cleaned, style["crop_box"], new_text, style["color_bgr"], bold, font_path=font_override)


def apply_replacement(image_bgr, old_text, new_text, lang, auto_yes=False, force_bold=None, font_override=None):
    bbox = None

    if old_text and pytesseract is not None:
        lines = ocr_lines(image_bgr, lang=lang)
        match = find_best_match(lines, old_text)
        if match and match[0] >= 55:
            score, line = match
            print(f"[OCR] Achou \"{line['text']}\" (similaridade {score:.0f}%, conf OCR {line['conf']:.0f}%)")
            if auto_yes or show_preview_and_confirm(image_bgr, line["bbox"], old_text):
                bbox = line["bbox"]
    elif old_text and pytesseract is None:
        print("[aviso] pytesseract não está instalado, indo direto pro modo manual.")

    if bbox is None:
        bbox = manual_select(image_bgr, old_text or new_text)
        if bbox is None:
            print(f"[aviso] Nenhuma área selecionada para \"{old_text or new_text}\", pulando.")
            return image_bgr

    return apply_at_bbox(image_bgr, bbox, new_text, force_bold=force_bold, font_override=font_override)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_replace_arg(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"Use o formato TEXTO_ANTIGO=TEXTO_NOVO, recebi: {value!r}")
    old, new = value.split("=", 1)
    return old.strip(), new.strip()


def main():
    parser = argparse.ArgumentParser(description="Troca textos em uma imagem de crachá mantendo o resto intocado.")
    parser.add_argument("imagem", help="Caminho da imagem do crachá")
    parser.add_argument("-o", "--output", help="Caminho de saída (padrão: <nome>_saida.<ext>)")
    parser.add_argument("--replace", action="append", type=parse_replace_arg, default=[],
                         metavar="ANTIGO=NOVO", help="Texto a substituir. Pode repetir a flag várias vezes.")
    parser.add_argument("--lang", default="por+eng", help="Idiomas do OCR (padrão: por+eng)")
    parser.add_argument("--yes", action="store_true", help="Aceita automaticamente o primeiro candidato do OCR, sem perguntar")
    parser.add_argument("--manual", action="store_true",
                         help="Modo interativo: pergunta repetidamente o que trocar, sem tentar OCR automático")
    bold_group = parser.add_mutually_exclusive_group()
    bold_group.add_argument("--bold", action="store_true", help="Força o texto novo em negrito (ignora a estimativa automática)")
    bold_group.add_argument("--no-bold", dest="no_bold", action="store_true", help="Força o texto novo sem negrito (ignora a estimativa automática)")
    parser.add_argument("--font", help="Caminho de um arquivo .ttf pra usar no texto novo, se souber a fonte exata do crachá")
    args = parser.parse_args()

    force_bold = True if args.bold else (False if args.no_bold else None)

    image_bgr = cv2.imread(args.imagem)
    if image_bgr is None:
        print(f"Não consegui abrir a imagem: {args.imagem}")
        sys.exit(1)

    replacements = list(args.replace)

    if args.manual or not replacements:
        print("Modo interativo. Deixe o texto antigo em branco pra ir direto pra seleção manual.")
        while True:
            old_text = input("\nTexto ANTIGO a procurar (ENTER para pular OCR e selecionar na mão, 'fim' pra parar): ").strip()
            if old_text.lower() == "fim":
                break
            new_text = input("Texto NOVO: ").strip()
            if not new_text:
                print("Texto novo vazio, ignorando essa troca.")
                continue
            replacements.append((old_text, new_text))
            more = input("Trocar mais algum texto nessa imagem? [s/N] ").strip().lower()
            if more not in ("s", "sim", "y", "yes"):
                break

    result = image_bgr
    for old_text, new_text in replacements:
        result = apply_replacement(result, old_text, new_text, args.lang, auto_yes=args.yes,
                                    force_bold=force_bold, font_override=args.font)

    if args.output:
        out_path = args.output
    else:
        base, ext = os.path.splitext(args.imagem)
        out_path = f"{base}_saida{ext or '.png'}"

    cv2.imwrite(out_path, result)
    print(f"\nSalvo em: {out_path}")


if __name__ == "__main__":
    main()
