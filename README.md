# Editor de Crachá

Troca texto em imagens de crachá (nome, cargo, data...) mantendo o fundo intocado, reposiciona e redimensiona o texto, ajusta a fonte, e gera folhas A4 com vários crachás diferentes — inclusive combinando modelos diferentes na mesma folha.

## Uso rápido

Abra **`editor_web.html`** direto no navegador — funciona 100% localmente (nenhuma imagem sai do seu computador), sem instalar nada. Também dá pra publicar como página web (é um arquivo HTML autocontido) e/ou levar o arquivo pra qualquer computador com navegador, mesmo sem internet.

### O que dá pra fazer
- Detectar e remover o texto antigo do crachá, reconstruindo o fundo (inclusive em fundos texturizados), só dentro da área selecionada.
- Reposicionar e redimensionar o texto (alças nos cantos), com controle manual de tamanho e cor da letra.
- 7 fontes prontas + carregar uma fonte personalizada (`.ttf`/`.otf`/`.woff`) do seu computador.
- Vários modelos de crachá ao mesmo tempo (abas), cada um com sua lista de pessoas e **seu próprio tamanho físico** (não compartilhado — editar o tamanho de um modelo não muda o dos outros).
- Adicionar vários crachás de uma vez (informando a quantidade) ou colando uma lista (uma linha por crachá, colunas separadas por Tab — cole direto de uma planilha).
- Gerar folha(s) A4, uma sequência de páginas por modelo (cada um no seu próprio tamanho/orientação), com paginação automática e opção de preencher o espaço sobrando com crachás menores.
- Responsivo — funciona de celular a desktop.
- Ctrl+Z desfaz a última alteração; Shift+Enter quebra linha nos campos de texto.

## Estrutura do projeto

- `editor_web.html` — o app principal, pronto pra usar (gerado, não editar direto).
- `editor_web_template.html` — código-fonte do app acima (HTML/CSS/JS), com placeholders no lugar das fontes.
- `build.py` — embute as fontes (base64) no template e gera `editor_web.html`. Rode `python3 build.py` depois de editar o template.
- `editor_cracha.py` — versão CLI em Python (OpenCV + Tesseract OCR), pra quem prefere linha de comando com detecção automática de texto via OCR.
- `app.py` — interface web local (Streamlit) pra rodar `editor_cracha.py` sem terminal.
- `abrir_app.sh` / `Editor de Cracha.desktop` — atalhos pra abrir a versão Streamlit com duplo clique.

A versão em `editor_web.html` é a recomendada pro uso do dia a dia — as versões Python (`editor_cracha.py`/`app.py`) ficam como alternativa pra quem quer detecção automática de texto via OCR, o que a versão web não faz (lá a seleção da área é manual, por design, pra funcionar de forma confiável em qualquer navegador sem dependências pesadas).
