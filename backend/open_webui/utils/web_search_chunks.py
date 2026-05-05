from typing import Optional, List
from dataclasses import dataclass
from urllib.parse import urlparse
import re

@dataclass
class WebSearchResult():
    title: str
    url: str
    domain: Optional[str] = None
    cited_text: Optional[str] = None

@dataclass
class InlineCitation():
    position: int
    source_indices: List[int]


def _get_web_search_results(delta, data): 
    provider_specific_fields = delta.get("provider_specific_fields", {})
    vertex_meta = data.get("vertex_ai_grounding_metadata")
    if provider_specific_fields:
        if provider_specific_fields.get("web_search_results"):
            return _claude_web_search_results(provider_specific_fields.get("web_search_results"))
    elif vertex_meta:
        return _gemini_web_search_results(vertex_meta)
    elif delta.get("content") and re.search(r'\[([^\]]+)\]\(([^)]+)\)', delta.get("content")):
        return _openai_web_search_results(delta.get("content"))
    
    return []

def _claude_web_search_results(web_search_results):
    web_search_result_list: List[WebSearchResult] = []
    if web_search_results:
        for result_group in web_search_results:
            for result in result_group.get("content", []):
                if result.get("type") == "web_search_result":
                    url = result.get("url", "")
                    title = result.get("title") or url
                    domain = urlparse(url).netloc[4:]
                    web_search_result_list.append(WebSearchResult(title, url, domain))
    return web_search_result_list

def _gemini_web_search_results(vertex_meta):
    web_search_result_list: List[WebSearchResult] = []
    chunks = vertex_meta[0].get("groundingChunks")
    if chunks:
        for i, chunk in enumerate(chunks):
            web = chunk.get("web") or {}
            url = web.get("uri", "")
            title = web.get("title") # title ist bereits domain
            # domain = web.get("domain")
            web_search_result_list.append(WebSearchResult(title, url))
    return web_search_result_list

def _openai_web_search_results(content):
    match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', content)
    if match:
        title = match.group(1)   # title ist bereits Domain
        url = match.group(2) 
        # domain = urlparse(url).netloc[4:]
        return([WebSearchResult(title, url)])


def _get_inline_citations(delta, data, content_blocks, sources):
    text_content = ""
    for block in content_blocks:
        if block["type"] == "text":
            text_content = f"{text_content}{block['content']}"
    text_content = text_content.encode("utf-8")
    provider_specific_fields = delta.get("provider_specific_fields", {})
    if provider_specific_fields:
        if provider_specific_fields.get("citation"):
            
            return _claude_inline_citations(provider_specific_fields, len(text_content), sources)
    if delta.get("content") and re.search(r'\[([^\]]+)\]\(([^)]+)\)', delta.get("content")):
        return _openai_inline_citations(delta.get("content"), len(text_content), sources)
    vertex_meta = data.get("vertex_ai_grounding_metadata")
    if vertex_meta:
        return _gemini_inline_citations(vertex_meta)
    return []

def _claude_inline_citations(provider_specific_fields, position, sources):
    citation = provider_specific_fields.get("citation")                         
    chunk_index = -1                                          
    if citation and citation.get("type") == "web_search_result_location":                                                                       
        url = citation.get("url")
        for i, source in enumerate(sources):
            if url == source.get("metadata")[0]['source']:
                chunk_index = i
        return([InlineCitation(position=position, source_indices=[chunk_index+1])])   
    return []
        
def _openai_inline_citations(content, position, sources):
    match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', content)
    if match:
        chunk_index = -1
        title = match.group(1)   # Teil in eckigen Klammern
        url = match.group(2)  # Teil in runden Klammern
        for i, source in enumerate(sources):
            if url == source.get("metadata")[0]['source']:
                chunk_index = i
        
        return([InlineCitation(position=position, source_indices={chunk_index + 1})])

def _gemini_inline_citations(vertex_meta):
    grounding_supports = vertex_meta[0].get("groundingSupports")
    print(grounding_supports)
    inline_citations: List[InlineCitation] = []
    if grounding_supports:
        supports_sorted = sorted( # sortieren, da sich sonst indizes im content ändern
            grounding_supports,
            key=lambda s: (s.get("segment") or {}).get("endIndex", 0),
            reverse=True,
        )
        for support in supports_sorted:
            end_index = (support.get("segment") or {}).get("endIndex", 0)
            chunk_indices = support.get("groundingChunkIndices") or []
            chunk_indices = [x + 1 for x in chunk_indices] 
            inline_citations.append(InlineCitation(position=end_index, source_indices=chunk_indices))
        return inline_citations
        
    return []
        
    

def inject_citations_into_content(inline_citation, content_blocks):
    last_text_block = next(
            (b for b in reversed(content_blocks) if b.get("type") == "text"),
            None,
        )
    if last_text_block is not None:
        text_bytes = last_text_block["content"].encode("utf-8")
        marker = " [" + ", ".join(str(i) for i in inline_citation.source_indices) + "] "
        text_bytes = (
            text_bytes[:inline_citation.position]
            + marker.encode("utf-8")
            + text_bytes[inline_citation.position:]
        )
        last_text_block["content"] = text_bytes.decode("utf-8", errors="replace")

    return content_blocks