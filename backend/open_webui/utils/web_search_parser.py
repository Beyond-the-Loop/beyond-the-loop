from typing import Optional, List
from dataclasses import dataclass
from urllib.parse import urlparse
import re

@dataclass
class WebSearchResult():
    url: str
    domain: str
    title: str
    cited_text: Optional[str] = None

@dataclass
class InlineCitation():
    position: int
    source_indices: List[int]
    utf_8_index: Optional[bool] = False


def get_web_search_results(delta, data): 
    provider_specific_fields = delta.get("provider_specific_fields", {})
    vertex_meta = data.get("vertex_ai_grounding_metadata")
    openai_url_citation = delta.get("openai_url_citation", {})
    if provider_specific_fields:
        if provider_specific_fields.get("web_search_results"):
            return _claude_web_search_results(provider_specific_fields.get("web_search_results"))
    if vertex_meta:
        return _gemini_web_search_results(vertex_meta)
    if openai_url_citation:
        return _openai_web_search_results(openai_url_citation)
    
    return []

def _claude_web_search_results(web_search_results):
    web_search_result_list: List[WebSearchResult] = []
    if web_search_results:
        for result_group in web_search_results:
            for result in result_group.get("content", []):
                if result.get("type") == "web_search_result":
                    url = result.get("url", "")
                    title = result.get("title") or url
                    domain = urlparse(url).netloc.removeprefix("www.")
                    web_search_result_list.append(WebSearchResult(url, domain, title))
    return web_search_result_list

def _gemini_web_search_results(vertex_meta):
    web_search_result_list: List[WebSearchResult] = []
    grounding_supports = vertex_meta[0].get("groundingSupports")
    chunks = vertex_meta[0].get("groundingChunks")
    if chunks:
        for i, chunk in enumerate(chunks):
            web = chunk.get("web") or {}
            url = web.get("uri", "")
            domain = web.get("domain") or web.get("title", "")
            # title = web.get("title", "")
            title = grounding_supports[i].get("segment").get("text")[:60] + "..."
            title = re.sub(r'[*_|]', '', title)
            web_search_result_list.append(WebSearchResult(url, domain, title))
    return web_search_result_list

def _openai_web_search_results(url_citations):
    web_search_result_list: List[WebSearchResult] = []
    for url_citation in url_citations:
        title = url_citation.get("title")
        url = url_citation.get("url")
        domain = urlparse(url).netloc.removeprefix("www.")
        web_search_result_list.append(WebSearchResult(url, domain, title))
    return(web_search_result_list)


def get_inline_citations(delta, data, sources):
    provider_specific_fields = delta.get("provider_specific_fields", {})
    if provider_specific_fields:
        if provider_specific_fields.get("citation"):
            return _claude_inline_citations(provider_specific_fields, sources)
    openai_url_citation = delta.get("openai_url_citation", {})
    if openai_url_citation:
        return _openai_inline_citations(delta.get("openai_url_citation", {}), sources)
    vertex_meta = data.get("vertex_ai_grounding_metadata")
    if vertex_meta:
        return _gemini_inline_citations(vertex_meta)
    return []

def _claude_inline_citations(provider_specific_fields, sources):
    citation = provider_specific_fields.get("citation")                         
    chunk_index = 0                                          
    if citation and citation.get("type") == "web_search_result_location":                                                                       
        url = citation.get("url")
        for i, source in enumerate(sources):
            if url == source.get("metadata")[0]['source']:
                chunk_index = i
        return([InlineCitation(position=-1, source_indices=[chunk_index+1])])   
    return []
        
def _openai_inline_citations(url_citations, sources):
    inline_citations: List[InlineCitation] = []
    citations_sorted = sorted( # sortieren, da sich sonst indizes im content ändern
            url_citations,
            key=lambda s: s.get("end_index", 0),
            reverse=True,
        )
    for url_citation in citations_sorted:
        position = url_citation.get("end_index")
        url = url_citation.get("url")
        chunk_index = -1
        for i, source in enumerate(sources):
            if url == source.get("metadata")[0]['source']:
                chunk_index = i
        inline_citations.append(InlineCitation(position=position, source_indices={chunk_index + 1}))
    
    return(inline_citations)

def _gemini_inline_citations(vertex_meta):
    grounding_supports = vertex_meta[0].get("groundingSupports")
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
            inline_citations.append(InlineCitation(position=end_index, source_indices=chunk_indices, utf_8_index = True))
        return inline_citations
        
    return []
        
    

def inject_citations_into_content(inline_citation, content_blocks, delta):
    if inline_citation.position == -1:
        marker = " [" + ", ".join(str(i) for i in inline_citation.source_indices) + "] "
        delta["content"] = str(marker)
        return content_blocks, delta
    last_text_block = next(
            (b for b in reversed(content_blocks) if b.get("type") == "text"),
            None,
        )
    if last_text_block is not None:
        text_stream = last_text_block["content"]
        marker = " [" + ", ".join(str(i) for i in inline_citation.source_indices) + "] "
        if inline_citation.utf_8_index:
            text_stream = text_stream.encode("utf-8")
            marker = marker.encode("utf-8")
        text_stream = (
            text_stream[:inline_citation.position]
            + marker
            + text_stream[inline_citation.position:]
        )
        if inline_citation.utf_8_index:
            text_stream = text_stream.decode("utf-8", errors="replace")

        last_text_block["content"] = text_stream

    return content_blocks, delta
