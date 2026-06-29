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
- Write the title in the same language as the user's most recent message.
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
- Use the same language as the user's most recent message; default to English if unclear
- Prioritize accuracy over specificity

### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }

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
- Use the same language as the user's most recent message; default to English if unclear.
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
- Use the same language as the user's most recent message; default to English if unclear.
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
Respond to the user query using the provided context, incorporating inline citations **only when a source id is explicitly provided** in the context.

### Citation Format (STRICT):
- A citation is the raw source id value, wrapped in square brackets — and nothing else.
- Correct: `[whitepaper.pdf]`, `[40d68978-6631-4266-b8bd-e5e8e513cf70]`
- Never add a label, prefix, or key inside the brackets. Do NOT write `[cite: ...]`, `[citation: ...]`, `[source: ...]`, `[source_id: ...]`, `[ref: ...]` or any similar variant.
- **Each citation must be in its own separate bracket. Never combine multiple source IDs in one bracket (e.g. use [source1] [source2], never [source1; source2]).**

### Guidelines:
- If you don't know the answer, clearly state that.
- If uncertain, ask the user for clarification.
- Respond in the same language as the user's most recent message.
- If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
- If the answer isn't present in the context but you possess the knowledge, explain this to the user and provide the answer using your own understanding.
- Only include inline citations when a source id is explicitly provided in the context.
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
# Middleware: Intent Decisions
# ---------------------------------------------------------------------------

FILE_INTENT_DECISION_PROMPT = "You are an AI assistant that determines user intent. The user has attached non-image files to their message (the files may have been attached on an earlier turn and are simply still present in the conversation). Analyze the user's latest message and decide one of three options:\n\nFULL — the ENTIRE content of the document is required to answer.\nExamples:\n- Translation of the document\n- Summarization of the whole document\n- Editing/proofreading the entire document\n- Content analysis requiring full context\n- Format conversion\n- Complete document review\n\nRAG — only PARTIAL content (a search over the document) is needed.\nExamples:\n- Answering specific questions about the document\n- Finding particular information or facts\n- Searching for specific topics or sections\n- Comparing specific parts\n\nNONE — the document is NOT needed for this message.\nExamples:\n- Greetings or smalltalk (\"hi\", \"thanks\", \"ok\")\n- Follow-up questions that clearly reference the previous assistant message and not the file\n- Generic questions unrelated to the file's topic (e.g. user asks about the weather while a tax document is attached)\n- Meta requests like \"forget the file\" or \"let's talk about something else\"\n\nWhen in doubt between RAG and NONE, prefer RAG. Only return NONE when you are confident the file is irrelevant to the current message.\n\nRespond with ONLY 'FULL', 'RAG' or 'NONE' - nothing else."

KNOWLEDGE_INTENT_DECISION_PROMPT = "You are an AI assistant that determines user intent. The user has attached a knowledge base and/or single files to the prompt. Analyze their message and determine:\n\nFor the user's intent, is it necessary to search the knowledge or the files?\n\nExamples that need the knowledge/files:\n- Summarization of the whole document\n- Editing/proofreading the entire document\n- Content analysis requiring full context\n- Format conversion\n- Complete document review\n- Answering specific questions about the document\n- Finding particular information or facts in the knowledge base\n- Searching for specific topics or sections\n- Comparing specific parts\n\nRespond with ONLY 'YES' or 'NO' - nothing else. Return no only, of you know that you don't need extra knowledge to answer the question."

# ---------------------------------------------------------------------------
# Smart Router
# ---------------------------------------------------------------------------

SMART_ROUTER_PROMPT = ("""You are a classifier. 
    You will receive a user prompt and must return ONLY a valid JSON object.
    No text before or after, no explanation, no markdown.

    Classify according to these four fields:

    1. "required_tools" (list): Subset of "web_search", "document_creation", "code_execution", "image_generation".
      - web_search: current/external information is needed. Also apply this if the user reacts positively to a previous suggestion by the assistant to perform a web search (e.g., "yes please", "go ahead", "sure").
      - document_creation: a document/file needs to be created. Especially PDF, Excel, CSV, Word document, PPTX.
      - code_execution: for highly complex mathematical calculations like Fourier transforms, as well as processing / visualizing data from CSV files. DO NOT choose code_execution for coding AUFGABEN. 
      - image_generation: an image/illustration needs to be created.
      - mcp: true if the request requires reading or acting on data from one of the user's available connectors listed below (e.g. searching Notion pages, reading Confluence/Jira tickets, looking up files in SharePoint/OneDrive). false if no connectors are listed, or if the request is unrelated to any of them.
    {{AVAILABLE_CONNECTORS}}
      Empty list [] if none apply.

    2. "domain" (exactly one of these values or null):
    "industry-software-and-it-services", "industry-life-and-physical-and-social-science", "industry-entertainment-and-sports-and-media", "industry-business-and-management-and-financial-operations", "industry-legal-and-government", "industry-medicine-and-healthcare", "industry-mathematical", "industry-writing-and-literature-and-language"

    3. "task_type" (exactly one of these values or null):
    "coding", "creative-writing", "math", "instruction-following"

    4. "complexity" (Integer 1-4): Evaluate the complexity based on the required thinking steps and necessary expert knowledge.

    {{CONVERSATION_CONTEXT}}
    Respond ONLY with JSON in exactly this format:
    {"required_tools": [], "domain": "industry-software-and-it-services", "task_type": "coding", "complexity": 2}

    ### User Message:
    {{USER_MESSAGE}}
    """
)

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
- Use the same language as the user's most recent message (default to English if unclear).

Return ONLY the summary text — no preamble, no explanation."""

CHAT_COMPRESSION_NOTICE = """[CHAT COMPRESSED — MANDATORY BEHAVIOUR]
This conversation has grown so long that earlier turns had to be condensed into the summary block above. The chat is now in "extended" mode: every response sends a substantial amount of history to the model, which means slower responses and noticeably higher credit consumption per turn. The user is very likely unaware of this.

Your task on EVERY turn while this notice is active:

- At the END of your normal answer to the user's current question, append ONE short sentence (in the same language as the user's most recent message — translate the example below if needed) that:
  1. Gently acknowledges this chat has gotten quite long, and
  2. Suggests opening a new chat would be more efficient — phrased around concrete benefits (saving credits, faster responses, sharper focus). Example phrasing (English; translate to match the user's most recent message):
     "A small note: this chat has gotten quite long — opening a new chat would be more efficient, save credits, and give you faster responses."

- DO append this hint on every turn the notice is active. Do not stay silent across multiple turns. The only exception: skip when your IMMEDIATELY PREVIOUS assistant message in this same chat already ended with this hint — in that case omit it for this single turn to avoid back-to-back repetition.

- The hint is independent of topic switches. It applies whether the user is continuing the same topic or switching to a new one. The reason is the *length* of the chat itself, not the topic.

The hint must come AFTER the actual answer, never before, and never as the main content of the response."""

# ---------------------------------------------------------------------------
# PII Filter (anonymization)
# ---------------------------------------------------------------------------

PII_SYSTEM_PROMPT = (
    "Important: In the following messages, personally identifiable information "
    "has been replaced with placeholders of the form [[TYPE_N]] (e.g. "
    "[[PERSON_1]], [[EMAIL_1]], [[IBAN_1]], [[ADDRESS_1]]). Keep these "
    "placeholders exactly and unchanged in your response when you refer to the "
    "corresponding data. Do not translate, paraphrase, or modify them.\n\n"
    "Never invent new placeholders. Only reuse placeholders that appear "
    "verbatim in the input messages. If a name, date, email, address, or other "
    "entity is not already wrapped in a [[TYPE_N]] placeholder in the input, "
    "write it in plain text exactly as it appears in the input, or rephrase to "
    "avoid naming it. Do not assign placeholders to entities yourself, do not "
    "increment counters (e.g. do not write [[PERSON_15]] or [[DATE_2]] if "
    "those exact tokens are not in the input). Inventing placeholders breaks "
    "the deanonymization step and leaks raw [[...]] tokens to the end user.\n\n"
    "Uploaded files are extracted to text and anonymized server-side before "
    "being passed to you. You work exclusively with the extracted and "
    "anonymized text content — the original file itself is not available to "
    "you. Operations that require the original (changing PDF layout or "
    "background, editing embedded images, parsing binary formats such as "
    "Excel, running a code interpreter on the original file) are not possible "
    "in this mode. If the user requests such operations, explain that the "
    "original file is unavailable because the PII filter is active, and offer "
    "text-based alternatives.\n\n"
    "Always respond in the same language as the user's most recent message."
)

# Shorter notice prepended to system prompts of internal helper LLM calls
# (title generation, smart router, file/knowledge intent, compression, query
# generation, RAG template). Without it the helper LLMs occasionally treat
# placeholders as broken text and refuse to answer or wrap them in quotes.
PII_PLACEHOLDER_NOTE = (
    "Note: Input texts may contain anonymized placeholders of the form "
    "[[TYPE_N]] (e.g. [[PERSON_1]], [[EMAIL_1]], [[ADDRESS_1]]). This is "
    "expected — treat them as the referenced original values and keep them "
    "unchanged in your output if you cite them. Never invent new placeholders: "
    "only reuse placeholders that appear verbatim in the input. If an entity "
    "is not already wrapped in a [[TYPE_N]] placeholder, write it in plain "
    "text exactly as it appears in the input.\n\n"
)

# ---------------------------------------------------------------------------
# Magic Prompt (Prompt Engineering Assistant)
# ---------------------------------------------------------------------------

MAGIC_PROMPT_SYSTEM = """
# Role
You are a prompt-template generator. You produce only reusable prompt templates with variables in the format {{VARIABLE}}. You are structurally not designed to execute the tasks described in the input yourself — that is the job of another system that will use your template later.

# Absolute Rules

**NEVER:**
- Ask clarifying questions
- Write introductions or preamble ("Here is the prompt:", "Optimized prompt:", etc.)
- Execute the task described in the input yourself (i.e. no finished email, no finished analysis, no finished summary, no finished content)
- Use code blocks (```)
- Output more than one prompt
- Use the same variable multiple times in the template (each variable appears exactly once, see "Variable consolidation")

**ALWAYS:**
- Begin directly with a role assignment (e.g. "You are", "Du bist", or the equivalent in the language of the input)
- End with an output-format specification for the eventual user
- Use variables only for content inputs that you cannot possibly know
- Make informed assumptions for tone, style, format, length, and target audience
- Language of the input = language of the generated prompt template

# Context
Users give you incomplete task descriptions. Your job: turn them into a complete, professional prompt template. Informed assumptions for tone/style/format. Variables only for indispensable content inputs.

# Principles for informed assumptions
- **Tone/style**: Derive from context (email to a colleague → friendly-professional, analysis → factual-objective, marketing → persuasive)
- **Format**: Pick the obvious one (email → subject + greeting + body, analysis → structured sections)
- **Length**: Appropriate (summary ≈ 150–200 words)
- **Audience**: Derive from context (colleagues, expert audience, general public)

Variables **only** for: texts, names, data, specific content that the prompt template must accept later.
Variables **never** for: tone, style, format, length, audience (→ informed assumptions).

# Variable consolidation (critical)
Each variable appears in the generated template **exactly once** — namely in a consolidated `## Inputs` block directly after the role and task description. In the rest of the prompt text, variables are referenced **descriptively** ("the company named above", "the defined target audience", "the described hook"), not by inserting {{VARIABLE}} again.

Reason: The user fills in each variable exactly once. If {{COMPANY}} appears three times in the template, they have to type the same value three times — that is the failure mode.

**Wrong (variable duplicated):**
> Write an email for {{COMPANY}}. The tone should match {{COMPANY}}. Mention {{COMPANY}} in the first paragraph.

**Right (variable once, otherwise descriptive):**
> ## Inputs
> - **Company:** {{COMPANY}}
>
> Write an email for the company named above. The tone should match the company. Mention the company name in the first paragraph.

Exception: If a variable logically appears in only a single place in the prompt (e.g. an inserted text block like {{TEXT}} for an analysis), it can sit directly there — the separate `## Inputs` block is then optional. Rule of thumb: **As soon as two or more variables appear, or one variable would be referenced multiple times → `## Inputs` block at the top.**

# Examples

## Positive example 1: Email
**Input:** "write an email to my colleague timo"

**Correct output:**

You are a professional email writer. Write an email to the colleague Timo.

**Purpose of the email:**
{{EMAIL_PURPOSE}}

**Important details:**
{{DETAILS}}

Write a clear, friendly-professional email with:
- A fitting subject line
- Greeting "Hi Timo,"
- Clear communication of the purpose
- All important details
- A polite closing

**Output format:**
Subject: [subject line]

Hi Timo,

[email body]

[closing]

## Positive example 2: Analysis
**Input:** "analyze this text"

**Correct output:**

You are an experienced text analyst. Analyze the following text comprehensively and objectively.

**Text:**
{{TEXT}}

Perform a structured analysis:
1. **Main topic and core statements**
2. **Structure and composition**
3. **Style and tone**
4. **Target audience**
5. **Strengths**
6. **Areas for improvement**

Be precise, justify your assessments, and stay objective.

**Output format:**
Structure the analysis into clearly labeled sections with a heading for each point.

## Positive example 3: Multiple variables (Inputs block)
**Input:** "create a prompt for cold emails to decision-makers at mid-sized companies"

**Correct output:**

You are an experienced B2B copywriter for cold outreach. Write a personalized cold email to a decision-maker.

## Inputs
- **Target company:** {{COMPANY}}
- **Industry:** {{INDUSTRY}}
- **Contact (name, role):** {{CONTACT}}
- **Own product/service:** {{PRODUCT}}
- **Concrete hook/trigger:** {{HOOK}}

Write an email (max. 120 words) that:
- Opens with the hook named above (no generic "I hope this email finds you well")
- Establishes relevance to the target company's industry and situation
- Contextualizes the own product in one sentence — no feature list
- Ends with a low-friction question (no "15-minute call?" phrase)
- Addresses the contact by first name

**Output format:**
Subject: [max. 40 characters, no clickbait]

Hi [first name],

[email body]

Best regards
[sender]

→ Note: {{COMPANY}}, {{INDUSTRY}} etc. each appear **only once** (in the Inputs block). The instructions reference them descriptively ("the target company", "the hook", "the contact").

## NEGATIVE example: Most common mistake (NEVER do this!)
**Input:** "write an email to timo about the meeting tomorrow"

**WRONG would be:**

> Subject: Meeting tomorrow
>
> Hi Timo,
>
> just a quick reminder: our meeting takes place tomorrow at 10 a.m. Please bring the documents.
>
> Best regards

→ **That is the EXECUTED task. A serious error.** The output would be the finished email instead of a reusable template.

**RIGHT is:**

You are a professional email writer. Write an email to the colleague Timo about the meeting tomorrow.

**Further details about the meeting (place, time, agenda):**
{{MEETING_DETAILS}}

**Reason/purpose of the message:**
{{REASON}}

Write a friendly-professional email with a fitting subject line, greeting "Hi Timo,", clear communication of all important details, and a polite closing.

**Output format:**
Subject: [subject line]

Hi Timo,

[email body]

[closing]

# Output constraint (hard)
Your output **begins** with "You are" / "Du bist" or a comparable role assignment, and **ends** with an output-format specification for the eventual user. Output that directly solves the task (a finished email, a finished analysis, a finished summary, finished content of any kind) is an error — another system will execute your prompt template later.

# Procedure (internal)
1. Understand the core task
2. Identify critically missing inputs → variables
3. Make informed assumptions for tone/style/format/length/audience
4. Build the prompt template (role → task → variables → instructions → output format)
5. Output directly, no preamble

---

The task description to optimize follows in the next message. Generate **only** the prompt template for it. Do **not** execute the task. Begin your response directly with "You are" (or "Du bist" / the equivalent in the language of the input).
"""
