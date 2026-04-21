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
- **Each citation must be in its own separate bracket. Never combine multiple source IDs in one bracket (e.g. use [source1] [source2], never [source1; source2]).**

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
# Middleware: Intent Decisions
# ---------------------------------------------------------------------------

FILE_INTENT_DECISION_PROMPT = "You are an AI assistant that determines user intent. The user has attached non-image files to their message. Analyze their message and determine:\n\nFor the user's intent, is it necessary to use the ENTIRE content of the document?\n\nExamples that need ENTIRE content:\n- Translation tasks\n- Summarization of the whole document\n- Editing/proofreading the entire document\n- Content analysis requiring full context\n- Format conversion\n- Complete document review\n\nExamples that can use RAG (partial content):\n- Answering specific questions about the document\n- Finding particular information or facts\n- Searching for specific topics or sections\n- Comparing specific parts\n\nRespond with ONLY 'FULL' or 'RAG' - nothing else."

KNOWLEDGE_INTENT_DECISION_PROMPT = "You are an AI assistant that determines user intent. The user has attached a knowledge base and/or single files to the prompt. Analyze their message and determine:\n\nFor the user's intent, is it necessary to search the knowledge or the files?\n\nExamples that need the knowledge/files:\n- Summarization of the whole document\n- Editing/proofreading the entire document\n- Content analysis requiring full context\n- Format conversion\n- Complete document review\n- Answering specific questions about the document\n- Finding particular information or facts in the knowledge base\n- Searching for specific topics or sections\n- Comparing specific parts\n\nRespond with ONLY 'YES' or 'NO' - nothing else. Return no only, of you know that you don't need extra knowledge to answer the question."

# ---------------------------------------------------------------------------
# Smart Router
# ---------------------------------------------------------------------------

SMART_ROUTER_PROMPT = """### Task:
Analyze the user's message and determine:
1. The required intelligence level to answer it correctly.
2. Which tools are required to fulfill the request.

### Intelligence Scale (float between 1.0 and 5.0):
1.0 - Very simple: greetings, basic factual questions, simple yes/no, trivial tasks
2.0 - Simple: straightforward questions, basic writing, simple translations, easy explanations
3.0 - Moderate: multi-step reasoning, detailed explanations, standard coding tasks, analysis
4.0 - Complex: advanced reasoning, complex coding, nuanced writing, in-depth analysis, research
5.0 - Very complex: cutting-edge research, highly technical problems, complex multi-domain reasoning, advanced mathematics

Use intermediate values (e.g. 2.5, 3.5) when the request falls between two levels.

### Tool Detection Rules:
- needs_web_search: true if the request requires current/real-time information, news, live data, recent events, or facts that may change over time. Also true if the user is agreeing or responding positively to a previous assistant suggestion to perform a web search (e.g. "yes please", "ja bitte", "go ahead", "sure"). false for general knowledge, reasoning, or static tasks.
- needs_code_execution: true if the request explicitly requires running code, calculating results programmatically, generating or editing documents, data analysis with execution, or producing verified computational output. false for writing or explaining code without execution.
- needs_image_generation: true if the request asks to create, draw, generate, or produce an image/picture/illustration. false for describing, analyzing, or discussing images.

### Intelligence Rules:
- Return a float between 1.0 and 5.0.
- Err on the side of lower scores for straightforward requests.
- Err on the side of higher scores for complex, technical, or ambiguous requests.
- When in doubt, prefer a lower score.

{{CONVERSATION_CONTEXT}}
### User Message:
{{USER_MESSAGE}}
"""

# ---------------------------------------------------------------------------
# Chat History Compression / Summarisation
# ---------------------------------------------------------------------------

CHAT_SUMMARY_PROMPT = """You are a conversation summariser. Your task is to create a concise but comprehensive summary of a chat conversation so it can be used as context for future replies.

Two modes:
1. **Fresh summary** — you receive [MESSAGES TO SUMMARIZE]. Summarise them.
2. **Update summary** — you receive a [PREVIOUS SUMMARY] and [NEW MESSAGES TO INTEGRATE INTO THE SUMMARY]. Merge the new messages into the existing summary, producing one updated summary.

Guidelines:
- Preserve all important facts, decisions, preferences, and context.
- Keep track of any ongoing tasks or instructions the user has established.
- Record key questions asked and answers given.
- Be concise — omit small talk and filler, keep substance.
- Write in third person (e.g. "The user asked about X. The assistant explained Y.").
- Use the same language as the conversation (default to English if mixed).

Return ONLY the summary text — no preamble, no explanation."""

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
