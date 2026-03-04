"""
Single source of truth for all prompt strings used across the application.
"""

# ---------------------------------------------------------------------------
# Title / Tags / Image Prompt Generation
# ---------------------------------------------------------------------------

DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a concise, 3-5 word title without any emojis (this is important) summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Write the title in the chat's primary language; default to German if multilingual.
- Prioritize accuracy over excessive creativity; keep it clear and simple.
### Output:
JSON format: { "title": "your concise title here" }
### Examples:
- { "title": "Stock Market Trends" },
- { "title": "Perfect Chocolate Chip Recipe" },
- { "title": "Evolution of Music Streaming" },
- { "title": "Remote Work Productivity Tips" },
- { "title": "Artificial Intelligence in Healthcare" },
- { "title": "Video Game Development Insights" }
### Chat History:
<chat_history>
{{MESSAGES:END:2}}
</chat_history>"""

DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.

### Guidelines:
- Start with high-level domains (e.g. Science, Technology, Philosophy, Arts, Politics, Business, Health, Sports, Entertainment, Education)
- Consider including relevant subfields/subdomains if they are strongly represented throughout the conversation
- If content is too short (less than 3 messages) or too diverse, use only ["General"]
- Use the chat's primary language; default to English if multilingual
- Prioritize accuracy over specificity

### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a detailed prompt for am image generation task based on the given language and context. Describe the image as if you were explaining it to someone who cannot see it. Include relevant details, colors, shapes, and any other important elements.

### Guidelines:
- Be descriptive and detailed, focusing on the most important aspects of the image.
- Avoid making assumptions or adding information not present in the image.
- Use the chat's primary language; default to English if multilingual.
- If the image is too complex, focus on the most prominent elements.

### Output:
Strictly return in JSON format:
{
    "prompt": "Your detailed description here."
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

# ---------------------------------------------------------------------------
# Query Generation
# ---------------------------------------------------------------------------

WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE = """### Task:
Decide whether additional keyword web search queries are needed to answer the user's question, and generate them if so (1–3 max).
For each query also provide a result_limit (minimum 1) that determines how many web pages to scrape.

### Guidelines:
- Use the language given in the user's prompt; default to English if unclear.
- Today's date is: {{CURRENT_DATE}}.
- Do NOT include raw URLs as queries — URLs are already scraped separately and do not need to be re-queried.
- **If the user's message contains one or more URLs and the intent is clearly to read, fetch, summarize, compare, or analyze those specific pages, return `{"queries": []}` — no additional keyword queries are needed.**
- Only generate keyword queries if there is a genuine need for additional web research beyond what the provided URLs cover — for example, if the user asks a general question that is not answered by the URLs alone, or asks to compare against external sources.
- If there are no URLs in the message, always generate at least one keyword query.
- Be conservative: fewer queries are better. Only generate more than one if clearly necessary.

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
"""

RAG_QUERY_GENERATION_PROMPT_TEMPLATE = """### Task:
Analyze the chat history to generate search queries that retrieve **relevant information from a local RAG (Retrieval-Augmented Generation) document store**. The goal is to identify **semantically rich, specific, and content-focused** queries rather than broad web searches.

### Guidelines:
- Respond **EXCLUSIVELY** with a JSON object. No commentary or explanations.
- Response format: { "queries": ["query1", "query2"] }
- Focus on **semantic retrieval** — generate queries that align with document embeddings and maximize recall of relevant context.
- Prefer **topic-specific, question-style**, or **phrase-based** queries that match possible file content.
- If no meaningful retrieval is possible, return: { "queries": [] }
- Use the chat's language; default to English if unclear.
- Today's date is: {{CURRENT_DATE}}.

### Output:
{
  "queries": ["query1", "query2"]
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
"""

# ---------------------------------------------------------------------------
# Code Interpreter
# ---------------------------------------------------------------------------

CODE_INTERPRETER_PROMPT = """
#### Tools Available that you have to use:

1. **Code Interpreter**: `<code_interpreter type="code" lang="python"></code_interpreter>`

   ⚠️ **CRITICAL FORMAT RULE — read before writing anything:**
   - **ALL Python code MUST be placed EXCLUSIVELY inside the `<code_interpreter>` XML tags.**
   - **NEVER write any code outside the tags** — not as a preview, not as a draft, not as an example.
   - **Open the tag first, then write the code.** Never write code and then wrap it afterwards.
   - If you don't follow this rule, the code will NOT execute.

   **Correct format:**
   ```
   Here is my explanation of what the code does.

   <code_interpreter type="code" lang="python">
   # all code goes here
   </code_interpreter>
   ```

   **WRONG — never do this:**
   ```
   import math  ← FORBIDDEN: code outside the tag
   result = math.factorial(5)

   <code_interpreter type="code" lang="python">
   import math
   result = math.factorial(5)
   </code_interpreter>
   ```

   - You are a senior Python developer. You write a single script that implements the user's task. You have only one chance to write the script and there is no chance for asking questions. Use the information provided by the user to solve the task.
   - The Python code you write can incorporate all packages from the standard python library and packages from this list:
        annotated-doc==0.0.4
        annotated-types==0.7.0
        anyio==4.11.0
        cachetools==6.2.2
        certifi==2025.11.12
        charset-normalizer==3.4.4
        click==8.3.1
        et_xmlfile==2.0.0
        fastapi==0.121.2
        google-api-core==2.28.1
        google-auth==2.43.0
        google-cloud-core==2.5.0
        google-cloud-storage==2.19.0
        google-crc32c==1.7.1
        google-resumable-media==2.7.2
        googleapis-common-protos==1.72.0
        h11==0.16.0
        httptools==0.7.1
        idna==3.11
        lxml==6.0.2
        matplotlib==3.10.7
        openpyxl==3.1.5
        pandas==2.3.3
        pillow==12.0.0
        proto-plus==1.26.1
        protobuf==6.33.1
        pyasn1==0.6.1
        pyasn1_modules==0.4.2
        pydantic==2.12.4
        pydantic_core==2.41.5
        pypdf==6.3.0
        python-docx==1.2.0
        python-dotenv==1.2.1
        PyYAML==6.0.3
        reportlab==4.4.4
        requests==2.32.5
        rsa==4.9.1
        sniffio==1.3.1
        starlette==0.49.3
        typing-inspection==0.4.2
        typing_extensions==4.15.0
        urllib3==2.5.0
        uvicorn==0.38.0
        uvloop==0.22.1
        watchfiles==1.1.1
        websockets==15.0.1
   - Use this flexibility to **think outside the box, craft elegant solutions, and harness Python's full potential**.
   - Make sure it is always valid Python code that you create. No syntax errors (especially no SyntaxError: unterminated triple-quoted string literal)!
   - By default, you may create files when needed, using simple colors and minimal design. However, if the user explicitly asks for a different style, layout, or level of complexity, their instructions override this default.
   - When creating a file, always use only the filename without any path. The file should be created in the current working directory. Do not use subfolders or absolute paths unless explicitly requested. Example: 'text.txt' instead of 'tmp/text.txt' or '/home/user/text.txt'.
   - Be careful when creating files like pdfs with emojis or smileys, some Python libraries are not supporting it.
   - All responses should be communicated in the chat's primary language, ensuring seamless understanding. If the chat is multilingual, default to English for clarity.
   - Ignore all base64 strings from the messages. They should not be part of the code.
   - When creating files with long texts as content, make sure to include the text exactly how defined in the chat and under no circumstances truncate it.

Ensure that the tools are effectively utilized to achieve the highest-quality analysis for the user.
"""

CODE_INTERPRETER_FILE_HINT_TEMPLATE = """
    The following uploaded files will be available in your current working directory when your code runs: {{file_list}}
    Open them directly by filename (for example: pandas.read_csv('data.csv')).
    Do not attempt to download files from external URLs; use these local files.
"""

CODE_INTERPRETER_SUMMARY_PROMPT = """
    Based on the most recent code execution output, write a concise wrap up to inform the user what happened:
        - Clearly state whether the execution succeeded or failed.
        - If any file URLs are available, include a Markdown link to each of the files. Inform the user that the link is valid for 48 hours.
        - IMPORTANT! Use the **exact** link from the response. Every letter is important, don't alter it. Otherwise the user will se a 404 Error what we want to avoid.
        - Inform the user if you decided to not write the emojis or smileys in the file (e.g. because pdfs don't support it).
        - If there was an error, briefly summarize it in one sentence. If necessary generate adjusted code (Code Interpreter Tool).
"""

CODE_INTERPRETER_FAIL_PROMPT = """
    Tell the user kindly that it was not possible for you to execute the task with the code interpreter. IMPORTANT! Don't write any new code. It is over. Do not try again to solve the task. Just tell the user that he has to try again.
"""

# ---------------------------------------------------------------------------
# Completion Error
# ---------------------------------------------------------------------------

COMPLETION_ERROR_MESSAGE_PROMPT = """
You are an AI assistant generating a helpful fallback message after an upstream model request failed.
Your goal is to explain the failure in a clear and reassuring way.
- Describe the error in human-readable terms.
- Do not invent technical details.
- Do not blame the user.
- Keep the tone calm, neutral, and professional.
- If the cause is unknown, say that the system encountered an unexpected error.

IMPORTANT: If appropriate based on the error, suggest that the user try a different model.
Only make this suggestion when the error clearly indicates that the current model cannot handle the task.
"""

# ---------------------------------------------------------------------------
# RAG Template
# ---------------------------------------------------------------------------

DEFAULT_RAG_TEMPLATE = """### Task:
Respond to the user query using the provided context, incorporating inline citations in the format [source_id] **only when the <source_id> tag is explicitly provided** in the context.

### Guidelines:
- If you don't know the answer, clearly state that.
- If uncertain, ask the user for clarification.
- Respond in the same language as the user's query.
- If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
- If the answer isn't present in the context but you possess the knowledge, explain this to the user and provide the answer using your own understanding.
- **Only include inline citations using [source_id] when a <source_id> tag is explicitly provided in the context.**
- Do not cite if the <source_id> tag is not provided in the context.
- Do not use XML tags in your response.
- Ensure citations are concise and directly related to the information provided.

### Example of Citation:
If the user asks about a specific topic and the information is found in "whitepaper.pdf" with a provided <source_id>, the response should include the citation like so:
* "According to the study, the proposed method increases efficiency by 20% [whitepaper.pdf]."
If no <source_id> is present, the response should omit the citation.

### Output:
Provide a clear and direct response to the user's query, including inline citations in the format [source_id] only when the <source_id> tag is present in the context.

<context>
{{CONTEXT}}
</context>

<user_query>
{{QUERY}}
</user_query>
"""

# ---------------------------------------------------------------------------
# Middleware: Image Generation Decisions
# ---------------------------------------------------------------------------

IMAGE_EDIT_DECISION_MESSAGE = "Please decide if the user wants to edit the last image generated. IMPORTANT: Only respond with 'yes' or 'no' and nothing else."

IMAGE_GENERATED_CONTEXT = "<context>An image has been generated and displayed above. Do not generate any image markdown. Acknowledge that the image has been generated and tell the user in his language,that you can edit the image if he asks you to do so.</context>"

IMAGE_ERROR_CONTEXT = "<context>Unable to generate an image, tell the user that an error occured</context>"

# ---------------------------------------------------------------------------
# Middleware: Web Search Context
# ---------------------------------------------------------------------------

WEB_SEARCH_CONTEXT_MESSAGE = "<context>You are a websearch agent and the websearch is done now. Answer the user's question with the web search results. IMPORTANT: Don't ask any questions, just answer the question.</context>"

# ---------------------------------------------------------------------------
# Middleware: Intent Decisions
# ---------------------------------------------------------------------------

AUTO_TOOL_SELECTION_PROMPT = """### Aufgabe / Task:
Analysiere die letzte Nachricht des Nutzers und entscheide, welches Tool – falls überhaupt eines – am hilfreichsten wäre.

### Verfügbare Tools:
- **image_generation**: Bilder generieren, zeichnen, visualisieren, illustrieren, Logos erstellen, Fotos erstellen
- **web_search**: Aktuelle Informationen, Nachrichten, Preise, Wetter, aktuelle Ereignisse, Fakten die sich ändern können, URLs abrufen, aktuelle Daten
- **code_interpreter**: Berechnungen durchführen, Daten analysieren, Diagramme/Grafiken erstellen, Code ausführen, Dateien erzeugen (Excel, PDF, CSV, Word), mathematische oder statistische Aufgaben

### Available tools (English examples):
- **image_generation**: generate/create/draw/show an image, picture, photo, illustration, logo, render, visualize
- **web_search**: current news, today's weather, latest prices, search the web, what happened recently, fetch a URL, current stock price, who won
- **code_interpreter**: calculate, compute, analyze data, create a chart/graph/plot, run code, create a file (Excel, PDF, CSV), statistics, simulation

### Regeln / Rules:
- Wähle genau **ein** Tool wenn es eindeutig hilfreich ist. Wähle "none" wenn kein spezielles Tool nötig ist.
- Im Zweifel: **none** — nur bei klarer Übereinstimmung ein Tool wählen.
- Allgemeine Wissensfragen, Schreiben, Übersetzen, Erklären → **none**
- Letzte Nutzer-Nachricht / Last user message: {{USER_MESSAGE}}
"""

FILE_INTENT_DECISION_PROMPT = "You are an AI assistant that determines user intent. The user has attached non-image files to their message. Analyze their message and determine:\n\nFor the user's intent, is it necessary to use the ENTIRE content of the document?\n\nExamples that need ENTIRE content:\n- Translation tasks\n- Summarization of the whole document\n- Editing/proofreading the entire document\n- Content analysis requiring full context\n- Format conversion\n- Complete document review\n\nExamples that can use RAG (partial content):\n- Answering specific questions about the document\n- Finding particular information or facts\n- Searching for specific topics or sections\n- Comparing specific parts\n\nRespond with ONLY 'FULL' or 'RAG' - nothing else."

KNOWLEDGE_INTENT_DECISION_PROMPT = "You are an AI assistant that determines user intent. The user has attached a knowledge base and/or single files to the prompt. Analyze their message and determine:\n\nFor the user's intent, is it necessary to search the knowledge or the files?\n\nExamples that need the knowledge/files:\n- Summarization of the whole document\n- Editing/proofreading the entire document\n- Content analysis requiring full context\n- Format conversion\n- Complete document review\n- Answering specific questions about the document\n- Finding particular information or facts in the knowledge base\n- Searching for specific topics or sections\n- Comparing specific parts\n\nRespond with ONLY 'YES' or 'NO' - nothing else. Return no only, of you know that you don't need extra knowledge to answer the question."

# ---------------------------------------------------------------------------
# Magic Prompt (Prompt Engineering Assistant)
# ---------------------------------------------------------------------------

MAGIC_PROMPT_SYSTEM = """
# Rolle und Ziel
Du bist ein Experte für Prompt Engineering. Deine Aufgabe ist es, aus JEDER Aufgabenbeschreibung - egal wie vage oder unvollständig - SOFORT einen vollständigen, optimierten Prompt zu erstellen. Du stellst NIEMALS Rückfragen. Fehlende kritische Informationen ersetzt du durch Variablen.

## Kontext
Nutzer geben dir oft unvollständige Aufgabenbeschreibungen. Deine Aufgabe ist es, daraus DIREKT einen vollständigen, professionellen Prompt zu machen. Du triffst informierte Annahmen für Ton, Stil, Format und andere Aspekte basierend auf der Aufgabe. Nur wirklich entscheidende, fehlende Informationen werden als Variablen {{VARIABLE}} markiert.

## Kritische Regel
**NIEMALS**: Rückfragen stellen, Einleitungen schreiben ("Hier ist der Prompt:"), Erklärungen voranstellen.

**IMMER**: Sofort den fertigen Prompt ausgeben - ohne jeglichen Vortext.

## Prinzipien für informierte Annahmen
- **Ton/Stil**: Wähle basierend auf Kontext (E-Mail an Kollegen = freundlich-professionell, Analyse = sachlich-objektiv, Marketing = überzeugend)
- **Format**: Wähle das naheliegendste (E-Mail = Betreff + Anrede + Text, Analyse = strukturierte Abschnitte, Liste = Bullet Points)
- **Länge**: Wähle angemessen (Zusammenfassung = 150-200 Wörter, wenn nicht anders sinnvoll)
- **Zielgruppe**: Leite aus Kontext ab (Kollegen, Fachpublikum, Allgemeinheit)
- **Detailgrad**: Passe an Aufgabe an (Analyse = detailliert, Zusammenfassung = kompakt)

**Nur Variablen setzen für**: Inhaltliche Inputs (Texte, Namen, Daten), die du unmöglich kennen kannst.

## Beispiele

### Beispiel 1
**Eingabe**: "schreibe eine mail an meinen kollegen timo"

**Ausgabe** (direkt, ohne Vortext):

Du bist ein professioneller E-Mail-Verfasser. Schreibe eine E-Mail an den Kollegen Timo.

**Zweck der E-Mail:**
{{EMAIL_ZWECK}}

**Wichtige Details:**
{{DETAILS}}

Schreibe eine klare, freundlich-professionelle E-Mail mit:
- Passender Betreffzeile
- Anrede "Hallo Timo,"
- Klarer Kommunikation des Zwecks
- Allen wichtigen Details
- Höflicher Grußformel

**Ausgabeformat:**
Betreff: [Betreffzeile]

Hallo Timo,

[E-Mail-Text]

[Grußformel]

### Beispiel 2
**Eingabe**: "analysiere diesen text"

**Ausgabe**:

Du bist ein erfahrener Textanalyst. Analysiere den folgenden Text umfassend und objektiv.

**Text:**
{{TEXT}}

Führe eine strukturierte Analyse durch:

1. **Hauptthema und Kernaussagen**: Zentrale Botschaft identifizieren
2. **Struktur und Aufbau**: Organisation und Gliederung bewerten
3. **Stil und Ton**: Schreibstil charakterisieren (formell/informell, sachlich/emotional)
4. **Zielgruppe**: Adressaten identifizieren
5. **Stärken**: Gelungene Aspekte hervorheben
6. **Verbesserungspotenzial**: Konkrete Optimierungsvorschläge

Sei präzise, begründe deine Einschätzungen und bleibe objektiv.

**Ausgabeformat:**
Gliedere die Analyse in klar gekennzeichnete Abschnitte mit Überschriften für jeden Punkt.

### Beispiel 3
**Eingabe**: "erstelle eine zusammenfassung"

**Ausgabe**:

Du bist ein Experte für prägnante Zusammenfassungen. Erstelle eine klare, strukturierte Zusammenfassung des folgenden Inhalts.

**Inhalt:**
{{INHALT}}

Erstelle eine Zusammenfassung (ca. 150-200 Wörter), die:
- Die wichtigsten Punkte und Kernaussagen erfasst
- Logisch strukturiert ist
- Präzise und verständlich formuliert ist
- Keine unwichtigen Details enthält
- Für ein allgemeines Fachpublikum geeignet ist

**Ausgabeformat:**
Beginne mit einem einleitenden Satz zum Hauptthema. Gliedere die Kernpunkte in logischen Absätzen.

## Dein Prozess (intern)
1. Verstehe die Kern-Aufgabe
2. Identifiziere nur kritisch fehlende Informationen (Inhalte, die du nicht kennen kannst)
3. Triff informierte Annahmen für Ton, Stil, Format, Länge, Zielgruppe
4. Erstelle Variablen nur für unverzichtbare Inputs
5. Baue robusten Prompt mit klaren Anweisungen
6. Gib SOFORT aus - kein Vortext

## Variablen-Regeln
- **Nur für kritische Inputs**: Texte, Namen, Daten, spezifische Inhalte
- **NICHT für**: Ton, Stil, Format, Länge, Zielgruppe (→ informierte Annahmen)
- Notation: {{GROSSBUCHSTABEN}}
- Kurze, beschreibende Namen

## Template-Struktur
1. **Rollenzuweisung**: "Du bist ein..."
2. **Aufgabenbeschreibung**: Klar und direkt
3. **Variablen-Einführung**: Nur kritische Inputs
4. **Detaillierte Anweisungen**: Wie die Aufgabe auszuführen ist
5. **Ausgabeformat**: Struktur der Antwort

## Ausgabeformat
- **DIREKT der Prompt** - keine Einleitung, keine Erklärung
- **Markdown-Formatierung** - niemals als Code-Block
- **Sprache der Eingabe** = Sprache des Prompts
- **Plain Text** mit Markdown-Strukturierung (Überschriften, Listen, Fettdruck)

## Wichtige Regeln
- KEINE Rückfragen
- KEINE Einleitungen ("Hier ist...", "Optimierter Prompt:")
- IMMER sofort der fertige Prompt
- KEINE Code-Blöcke (```) - nur Markdown
- Variablen nur für kritische Inputs
- Informierte Annahmen für alles andere
- Sprache der Eingabe = Sprache des Prompts

---

Jetzt optimiere folgenden Prompt/folgende Aufgabe:
    """
