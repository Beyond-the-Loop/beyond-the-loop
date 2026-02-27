import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import re
import html
from urllib.parse import urlparse, urlunparse

log = logging.getLogger(__name__)


import site
from fpdf import FPDF

from open_webui.env import STATIC_DIR
from beyond_the_loop.models.chats import ChatTitleMessagesForm
from open_webui.env import FONTS_DIR


def _extract_url_from_source_obj(obj: dict) -> str | None:
    """
    Try to pull a URL from your source object shape.
    Priority: source.name (if URL) -> document[0] -> metadata[0].source
    """
    if not isinstance(obj, dict):
        return None

    candidates = []
    try:
        candidates.append(obj.get("source", {}).get("name"))
    except Exception:
        pass

    try:
        docs = obj.get("document")
        if isinstance(docs, list) and docs:
            candidates.append(docs[0])
    except Exception:
        pass

    try:
        meta = obj.get("metadata")
        if isinstance(meta, list) and meta:
            candidates.append(meta[0].get("source"))
    except Exception:
        pass

    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return None

def _normalize_url(url: str) -> str:
    """
    Normalize URL for deduping:
    - lower-case host
    - strip default ports
    - remove trailing slash (except root)
    """
    try:
        p = urlparse(url)
        netloc = p.hostname.lower() if p.hostname else ""
        if p.port and not ((p.scheme == "http" and p.port == 80) or (p.scheme == "https" and p.port == 443)):
            netloc = f"{netloc}:{p.port}"
        path = p.path
        if path.endswith("/") and path != "/":
            path = path[:-1]
        return urlunparse((p.scheme, netloc, path, p.params, p.query, p.fragment))
    except Exception:
        # If parsing fails, return original; dedupe may be looser.
        return url

def _remap_citations_to_global(content: str, message_sources: list,
                               url_to_idx: dict, global_sources: list[dict]) -> str:
    """
    Replace [n] in content with global indices based on the message's sources list.
    url_to_idx: dict[normalized_url] -> global 1-based index
    global_sources: list of {'url': str, 'title': Optional[str]}
    """
    if not isinstance(message_sources, list) or not message_sources:
        return content

    def repl(m: re.Match):
        try:
            n = int(m.group(1))
        except Exception:
            return m.group(0)

        src_obj = message_sources[n - 1] if 1 <= n <= len(message_sources) else None
        if not src_obj:
            return m.group(0)

        raw = _extract_url_from_source_obj(src_obj)
        if not raw:
            return m.group(0)

        norm = _normalize_url(raw)
        if norm not in url_to_idx:
            # Optional: a human-ish title if name != URL
            title = None
            try:
                name = src_obj.get("source", {}).get("name")
                if isinstance(name, str) and name and name != raw:
                    title = name
            except Exception:
                pass
            global_sources.append({"url": norm, "title": title})
            url_to_idx[norm] = len(global_sources)  # 1-based
        return f"[{url_to_idx[norm]}]"

    return re.sub(r"\[(\d+)\]", repl, content)

def _render_sources_section(global_sources: list[dict]) -> str:
    if not global_sources:
        return ""
    # Minimal styling—FPDF HTML supports basic tags
    items = []
    for i, s in enumerate(global_sources, start=1):
        url = s["url"]
        safe_url = html.escape(url)
        title = s.get("title")
        if isinstance(title, str) and title.strip() and title.strip() != url:
            safe_title = html.escape(title.strip())
            items.append(f'<li>[{i}] {safe_title} — <a href="{safe_url}">{safe_url}</a></li>')
        else:
            items.append(f'<li>[{i}] <a href="{safe_url}">{safe_url}</a></li>')
    return f"""
<hr>
<h2>Sources</h2>
<ol>
{''.join(items)}
</ol>
"""


class PDFGenerator:
    """
    Description:
    The `PDFGenerator` class is designed to create PDF documents from chat messages.
    The process involves transforming markdown content into HTML and then into a PDF format

    Attributes:
    - `form_data`: An instance of `ChatTitleMessagesForm` containing title and messages.

    """

    def __init__(self, form_data: ChatTitleMessagesForm):
        self.html_body = None
        self.messages_html = None
        self.form_data = form_data

        self.css = Path(STATIC_DIR / "assets" / "pdf-style.css").read_text()

    def format_timestamp(self, timestamp: float) -> str:
        """Convert a UNIX timestamp to a formatted date string."""
        try:
            date_time = datetime.fromtimestamp(timestamp)
            return date_time.strftime("%Y-%m-%d, %H:%M:%S")
        except (ValueError, TypeError) as e:
            # Log the error if necessary
            return ""

    def _build_html_message(self, message: Dict[str, Any]) -> str:
        """Build HTML for a single message."""
        role = message.get("role", "user")
        content = message.get("content", "")
        timestamp = message.get("timestamp")

        model = message.get("model") if role == "assistant" else ""

        date_str = self.format_timestamp(timestamp) if timestamp else ""

        # extends pymdownx extension to convert markdown to html.
        # - https://facelessuser.github.io/pymdown-extensions/usage_notes/
        # html_content = markdown(content, extensions=["pymdownx.extra"])

        content = content.replace("\n", "<br/>")
        html_message = f"""
            <div>
                <div>
                    <h4>
                        <strong>{role.title()}</strong>
                        <span style="font-size: 12px;">{model}</span>
                    </h4>
                    <div> {date_str} </div>
                </div>
                <br/>
                <br/>

                <div>
                    {content}
                </div>
            </div>
            <br/>
          """
        return html_message

    def _generate_html_body(self) -> str:
        """Generate the full HTML body for the PDF."""
        return f"""
        <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            </head>
            <body>
            <div>
                <div>
                    <h2>{self.form_data.title}</h2>
                    {self.messages_html}
                </div>
            </div>
            </body>
        </html>
        """

    def generate_chat_pdf(self) -> bytes:
        """
        Generate a PDF from chat messages.
        """
        try:
            global FONTS_DIR

            pdf = FPDF()
            pdf.add_page()

            # When running using `pip install` the static directory is in the site packages.
            if not FONTS_DIR.exists():
                FONTS_DIR = Path(site.getsitepackages()[0]) / "static/fonts"
            # When running using `pip install -e .` the static directory is in the site packages.
            # This path only works if `open-webui serve` is run from the root of this project.
            if not FONTS_DIR.exists():
                FONTS_DIR = Path("./backend/static/fonts")

            pdf.add_font("NotoSans", "", f"{FONTS_DIR}/NotoSans-Regular.ttf")
            pdf.add_font("NotoSans", "b", f"{FONTS_DIR}/NotoSans-Bold.ttf")
            pdf.add_font("NotoSans", "i", f"{FONTS_DIR}/NotoSans-Italic.ttf")
            pdf.add_font("NotoSansKR", "", f"{FONTS_DIR}/NotoSansKR-Regular.ttf")
            pdf.add_font("NotoSansJP", "", f"{FONTS_DIR}/NotoSansJP-Regular.ttf")
            pdf.add_font("NotoSansSC", "", f"{FONTS_DIR}/NotoSansSC-Regular.ttf")
            pdf.add_font("Twemoji", "", f"{FONTS_DIR}/Twemoji.ttf")

            pdf.set_font("NotoSans", size=12)
            pdf.set_fallback_fonts(
                ["NotoSansKR", "NotoSansJP", "NotoSansSC", "Twemoji"]
            )

            pdf.set_auto_page_break(auto=True, margin=15)

            # --- Build HTML with globalized citations ---
            # Collect global bibliography
            url_to_global_idx: dict[str, int] = {}
            global_sources: list[dict] = []

            # If your _build_html_message reads from message.content,
            # create a shallow copy with remapped content before building HTML.
            rendered_messages_html: list[str] = []
            for msg in self.form_data.messages:
                # Pull sources array (support either .sources or .source)
                msg_sources = None
                if isinstance(msg, dict):
                    if isinstance(msg.get("sources"), list):
                        msg_sources = msg["sources"]
                    elif isinstance(msg.get("source"), list):
                        msg_sources = msg["source"]

                # Remap [n] to global indices
                content = msg.get("content", "")
                remapped = _remap_citations_to_global(
                    content,
                    msg_sources or [],
                    url_to_global_idx,
                    global_sources,
                )

                # Build HTML using the remapped content
                msg_copy = dict(msg)
                msg_copy["content"] = remapped

                rendered_messages_html.append(self._build_html_message(msg_copy))
                
            # Combine messages
            self.messages_html = "<div>" + "".join(rendered_messages_html) + "</div>"
            log.debug(f"messages_html: {self.messages_html}")
            # Generate full body (your method can insert headers, styles, etc.)
            self.html_body = self._generate_html_body() 

            # Append Sources section if any
            sources_html = _render_sources_section(global_sources)
            full_html = self.html_body + sources_html

            pdf.write_html(full_html)

            # Output bytes
            pdf_bytes = pdf.output()
            return bytes(pdf_bytes)

            # Build HTML messages
            # messages_html_list: List[str] = [
            #     self._build_html_message(msg) for msg in self.form_data.messages
            # ]
            # self.messages_html = "<div>" + "".join(messages_html_list) + "</div>"

            # # Generate full HTML body
            # self.html_body = self._generate_html_body()

            # pdf.write_html(self.html_body)

            # # Save the pdf with name .pdf
            # pdf_bytes = pdf.output()

            # return bytes(pdf_bytes)
        except Exception as e:
            raise e
