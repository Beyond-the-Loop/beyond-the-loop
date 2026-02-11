import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import aiohttp
import requests

import os

from aiohttp import ClientResponseError
from fastapi import Depends, HTTPException, Request, APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from beyond_the_loop.models.models import Models
from beyond_the_loop.models.completions import Completions
from litellm.utils import trim_messages


from beyond_the_loop.config import (
    CACHE_DIR,
)
from beyond_the_loop.config import DEFAULT_AGENT_MODEL
from beyond_the_loop.config import COMPLETION_ERROR_MESSAGE_PROMPT
from open_webui.env import (
    AIOHTTP_CLIENT_TIMEOUT,
    AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST,
    ENABLE_FORWARD_USER_INFO_HEADERS,
)

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS


from open_webui.utils.payload import (
    apply_model_params_to_body_openai,
    apply_model_system_prompt_to_body,
)

from open_webui.utils.auth import get_verified_user, get_current_api_key_user
from beyond_the_loop.utils.access_control import has_access
from beyond_the_loop.services.credit_service import credit_service
from beyond_the_loop.services.payments_service import payments_service
from beyond_the_loop.services.fair_model_usage_service import fair_model_usage_service

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OPENAI"])

##########################################
#
# Utility functions
#
##########################################

session: aiohttp.ClientSession | None = None

async def _get_session() -> aiohttp.ClientSession:
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            trust_env=True,
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
            connector=aiohttp.TCPConnector(limit=100)  # limits concurrent connections
        )
    return session

async def send_get_request(url, key=None):
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(
                url, headers={**({"Authorization": f"Bearer {key}"} if key else {})}
            ) as response:
                return await response.json()
    except Exception as e:
        # Handle connection error here
        log.error(f"Connection error: {e}")
        return None


async def cleanup_response(
    response: Optional[aiohttp.ClientResponse],
    session: Optional[aiohttp.ClientSession],
):
    if response:
        response.close()
    if session:
        await session.close()


##########################################
#
# Model management functions
#
##########################################

async def get_all_models():
    """
    Fetch all available models from the litellm server.
    Returns the models in OpenAI API format.
    """
    try:
        url = f"{os.getenv('OPENAI_API_BASE_URL')}/models"
        api_key = os.getenv('OPENAI_API_KEY')
        
        log.info(f"Fetching models from litellm server: {url}")

        response = await send_get_request(url, api_key)
        
        if response is None:
            log.error("Failed to fetch models from litellm server")
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch models from litellm server"
            )
        
        log.info(f"Successfully fetched {len(response.get('data', []))} models from litellm")
        return response
        
    except Exception as e:
        log.error(f"Error fetching models from litellm: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching models: {str(e)}"
        )

##########################################
#
# API routes
#
##########################################

router = APIRouter()

@router.post("/audio/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    try:
        body = await request.body()
        name = hashlib.sha256(body).hexdigest()

        SPEECH_CACHE_DIR = Path(CACHE_DIR).joinpath("./audio/speech/")
        SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = SPEECH_CACHE_DIR.joinpath(f"{name}.mp3")
        file_body_path = SPEECH_CACHE_DIR.joinpath(f"{name}.json")

        # Check if the file already exists in the cache
        if file_path.is_file():
            return FileResponse(file_path)

        r = None
        try:
            r = requests.post(
                url=f"{os.getenv('OPENAI_API_BASE_URL')}/audio/speech",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    **(
                        {
                            "X-OpenWebUI-User-Name": user.first_name + " " + user.last_name,
                            "X-OpenWebUI-User-Id": user.id,
                            "X-OpenWebUI-User-Email": user.email,
                            "X-OpenWebUI-User-Role": user.role,
                        }
                        if ENABLE_FORWARD_USER_INFO_HEADERS
                        else {}
                    ),
                },
                stream=True,
            )

            r.raise_for_status()

            # Save the streaming content to a file
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            with open(file_body_path, "w") as f:
                json.dump(json.loads(body.decode("utf-8")), f)

            # Return the saved file
            return FileResponse(file_path)

        except Exception as e:
            log.exception(e)

            detail = None
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        detail = f"External: {res['error']}"
                except Exception:
                    detail = f"External: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500,
                detail=detail if detail else "Server Connection Error",
            )

    except ValueError:
        raise HTTPException(status_code=401, detail=ERROR_MESSAGES.OPENAI_NOT_FOUND)

@router.post("/chat/completions")
async def generate_chat_completion(
        form_data: dict,
        user=Depends(get_verified_user)
):
    payload = {**form_data}
    metadata = payload.pop("metadata", {})

    agent_or_task_prompt = metadata.get("agent_or_task_prompt", False)

    model_info = Models.get_model_by_id(form_data.get("model"))

    if model_info is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found. Please check the model ID is correct.",
        )

    has_chat_id = "chat_id" in metadata and metadata["chat_id"] is not None

    if model_info.base_model_id:
        model_name = model_info.base_model_id if model_info.user_id == "system" else Models.get_model_by_id(model_info.base_model_id).name
    else:
        model_name = model_info.name

    payload["model"] = model_name

    if model_name == "Mistral Large 2":
        payload["stream"] = False
        for message in payload["messages"]:
            if "content" in message and isinstance(message["content"], list):
                message["content"] = [
                    c for c in message["content"]
                    if c.get("type") != "image_url"
                ]

    subscription = payments_service.get_subscription(user.company_id)

    if (has_chat_id or agent_or_task_prompt) and subscription.get("plan") != "free" and subscription.get("plan") != "premium":
        await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)

    params = model_info.params.model_dump()
    payload = apply_model_params_to_body_openai(params, payload)
    payload = apply_model_system_prompt_to_body(params, payload, metadata, user)

    # Check model access
    if not agent_or_task_prompt and not(
        model_info.is_active and (user.id == model_info.user_id or (not model_info.base_model_id and user.role == "admin") or has_access(
            user.id, type="read", access_control=model_info.access_control
        ))
    ):
        raise HTTPException(
            status_code=403,
            detail="Model not found, no access for user",
        )

    # Check model fair usage
    if not agent_or_task_prompt and (subscription.get("plan") == "free" or subscription.get("plan") == "premium"):
        fair_model_usage_service.check_for_fair_model_usage(user, payload["model"], subscription.get("plan"))

    if payload["stream"]:
        payload["stream_options"] = {"include_usage": True}

    # History shortening (TODO: Find a better place for this)
    # Mapping internal model names to provider/base models
    MODEL_MAPPING = {
        "Claude 4.5 Haiku": "vertex_ai/claude-haiku-4-5@20251001",
        "Claude Sonnet 4.5": "vertex_ai/claude-sonnet-4-5@20250929",
        "Google 2.5 Flash": "gemini-2.5-flash",
        "Google 2.5 Pro": "gemini-2.5-pro",
        "GPT o3": "azure/o3",
        "GPT o4-mini": "azure/o4-mini",
        "GPT-5": "azure/gpt-5",
        "GPT-5 mini": "azure/gpt-5-mini",
        "GPT-5 nano": "azure/gpt-5-nano",
        "Grok 4": "xai/grok-4",
        "Mistral Large 2": "vertex_ai/mistral-large-2411@001",
        "Perplexity Sonar Deep Research": "perplexity/sonar-deep-research",
        "Perplexity Sonar Pro": "perplexity/sonar-pro",
        "Perplexity Sonar Reasoning Pro": "perplexity/sonar-reasoning-pro",
        "GPT-5.1 instant": "azure/gpt-5.1-chat",
        "GPT-5.1 thinking": "azure/gpt-5.1",
    }

    try:
        payload["messages"] = trim_messages(payload["messages"], MODEL_MAPPING[model_name])
    except Exception:
        print("Error trimming messages, continuing with the original messages...")

    # Convert the modified body back to JSON
    payload = json.dumps(payload)

    r = None
    session = None
    streaming = False
    response = None

    # Parse payload once for both streaming and non-streaming cases
    payload_dict = json.loads(payload)
    last_user_message = next((msg['content'] for msg in reversed(payload_dict['messages']) if msg['role'] == 'user'), '')

    try:
        s = await _get_session()

        r = await s.request(
            method="POST",
            url=f"{os.getenv('OPENAI_API_BASE_URL')}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "Content-Type": "application/json",
                **(
                    {
                        "X-OpenWebUI-User-Name": user.first_name + " " + user.last_name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS
                    else {}
                ),
            },
        )

        # Check if response is SSE
        if "text/event-stream" in r.headers.get("Content-Type", ""):
            streaming = True

            async def insert_completion_if_streaming_is_done():
                full_response = ""
                async for chunk in r.content:
                    chunk_str = chunk.decode()
                    if chunk_str.startswith('data: '):
                        try:
                            data = json.loads(chunk_str[6:])
                            delta = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if delta:  # Only use it if there's actual content
                                full_response += delta
                            elif data.get('usage'):
                                # End of stream
                                # Add completion to completion table if it's a chat message from the user
                                credit_cost_streaming = 0

                                if has_chat_id and subscription.get("plan") != "free" and subscription.get("plan") != "premium":
                                    credit_cost_streaming = await credit_service.subtract_credit_cost_by_user_and_response_and_model(user, data, model_name)

                                Completions.insert_new_completion(user.id, model_name, credit_cost_streaming, model_info.name if model_info.base_model_id else None, agent_or_task_prompt)
                        except json.JSONDecodeError:
                            print(f"\n{chunk_str}")

                    yield chunk

            return StreamingResponse(
                insert_completion_if_streaming_is_done(),
                status_code=r.status,
                headers=dict(r.headers),
                background=BackgroundTask(
                    cleanup_response, response=r, session=session
                ),
            )
        else:
            try:
                response = await r.json()
            except Exception as e:
                print(e)
                response = await r.text()

            try:
                r.raise_for_status()
            except ClientResponseError as e:
                print(e)
                if agent_or_task_prompt:
                    raise e

                model = Models.get_model_by_name_and_company(DEFAULT_AGENT_MODEL.value, user.company_id)

                form_data = {
                    "model": model.id,
                    "messages": [
                        {
                            "role": "assistant",
                            "content": COMPLETION_ERROR_MESSAGE_PROMPT
                        },
                        {
                            "role": "user",
                            "content": str(response)
                        }],
                    "stream": False,
                    "metadata": {
                        "chat_id": None,
                        "agent_or_task_prompt": True
                    },
                    "temperature": 0.0
                }

                return await generate_chat_completion(form_data, user)

            credit_cost = 0

            # Add completion to completion table
            response_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')

            if has_chat_id and subscription.get("plan") != "free" and subscription.get("plan") != "premium":
                credit_cost = await credit_service.subtract_credit_cost_by_user_and_response_and_model(user, response, model_name)

            Completions.insert_new_completion(user.id, model_name, credit_cost, model_info.name if model_info.base_model_id else None, agent_or_task_prompt)

            return response
    except Exception as e:
        print(e)

        detail = None
        if isinstance(response, dict):
            if "error" in response:
                detail = f"{response['error']['message'] if 'message' in response['error'] else response['error']}"
        elif isinstance(response, str):
            detail = response

        raise HTTPException(
            status_code=r.status if r else 500,
            detail=detail if detail else "Server Connection Error",
        )
    finally:
        if not streaming and session:
            if r and isinstance(r, aiohttp.ClientResponse):
                r.close()
            await session.close()

@router.post("/magicPrompt")
async def generate_prompt(form_data: dict, user=Depends(get_verified_user)):
    model = Models.get_model_by_name_and_company(DEFAULT_AGENT_MODEL.value, user.company_id)

    thore_test = """
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

    form_data = {
        "model": model.id,
        "messages": [
            {
                "role": "assistant",
                "content": thore_test
            },
            {
                "role": "user",
                "content":  form_data["prompt"]
            }],
        "stream": False,
        "metadata": {
            "chat_id": None,
            "agent_or_task_prompt": True
        },
        "temperature": 0.0
    }

    message = await generate_chat_completion(form_data, user)

    return message['choices'][0]['message']['content']