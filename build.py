#!/usr/bin/env python3
"""Embute as fontes (base64) no template e gera index.html.

Uso:
    python3 build.py
"""

import base64
import os

FONT_MAP = {
    "__FONT_SANS_REG__": "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    "__FONT_SANS_BOLD__": "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    "__FONT_SERIF_REG__": "/usr/share/fonts/dejavu-serif-fonts/DejaVuSerif.ttf",
    "__FONT_SERIF_BOLD__": "/usr/share/fonts/dejavu-serif-fonts/DejaVuSerif-Bold.ttf",
    "__FONT_MONO_REG__": "/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf",
    "__FONT_MONO_BOLD__": "/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono-Bold.ttf",
    "__FONT_SANS2_REG__": "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
    "__FONT_SANS2_BOLD__": "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf",
    "__FONT_SERIF2_REG__": "/usr/share/fonts/liberation-serif/LiberationSerif-Regular.ttf",
    "__FONT_SERIF2_BOLD__": "/usr/share/fonts/liberation-serif/LiberationSerif-Bold.ttf",
    "__FONT_ROUNDED_REG__": "/usr/share/fonts/urw-base35/URWGothic-Book.otf",
    "__FONT_ROUNDED_BOLD__": "/usr/share/fonts/urw-base35/URWGothic-Demi.otf",
    "__FONT_SLAB_REG__": "/usr/share/fonts/urw-base35/URWBookman-Light.otf",
    "__FONT_SLAB_BOLD__": "/usr/share/fonts/urw-base35/URWBookman-Demi.otf",
}


def data_uri(path):
    with open(path, "rb") as f:
        raw = f.read()
    return "data:font/ttf;charset=utf-8;base64," + base64.b64encode(raw).decode("ascii")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(here, "index_template.html")
    output_path = os.path.join(here, "index.html")

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    for placeholder, font_path in FONT_MAP.items():
        if placeholder not in content:
            print(f"aviso: placeholder nao encontrado: {placeholder}")
            continue
        if not os.path.exists(font_path):
            raise SystemExit(
                f"Fonte nao encontrada: {font_path}\n"
                f"Ajuste FONT_MAP em build.py para o caminho correto no seu sistema "
                f"(DejaVu, Liberation e URW Base 35 costumam vir com o pacote fonts padrao "
                f"de distribuicoes Linux; no Fedora/RHEL/Rocky: dejavu-sans-fonts, "
                f"liberation-sans, liberation-serif, urw-base35-fonts)."
            )
        content = content.replace(placeholder, data_uri(font_path))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"gerado: {output_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
