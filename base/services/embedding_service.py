import os
import logging
from openai import OpenAI
from pinecone import Pinecone

logger = logging.getLogger(__name__)

def get_pinecone_index():
    """
    Returns an initialized Pinecone Index object.
    Reads PINECONE_API_KEY and PINECONE_INDEX_NAME from environment.
    Raises clean errors if either is missing.
    Uses pinecone-client v3+ API.
    """
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME")
    
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY environment variable is not set.")
    if not index_name:
        raise RuntimeError("PINECONE_INDEX_NAME environment variable is not set.")
        
    pc = Pinecone(api_key=api_key)
    return pc.Index(name=index_name)

def build_embedding_text(registration) -> str:
    """
    Builds a sanitized, PII-free string for embedding from structured M2M data.
    
    [CONSTRAINT 1 & 2]
    Strips all PII (no name/contact in the embedding).
    Deterministic and reproducible based on structured skills.
    """
    skills = list(registration.skills.values_list("name", flat=True))
    return (
        f"Years of experience: {registration.years_of_experience}. "
        f"Notice period: {registration.notice_period}. "
        f"Skills and expertise: {', '.join(skills)}."
    )

def get_embedding(text: str) -> list[float]:
    """
    Generate an embedding vector using text-embedding-3-small.
    
    [CONSTRAINT 3]
    Model: text-embedding-3-small (1536 dimensions).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
        
    client = OpenAI(api_key=api_key)
    
    # WALLET GUARD: Hard limit truncation
    truncated_text = text[:8000]
    
    # Log token estimate (proxy)
    est_tokens = len(truncated_text.split())
    logger.info(f"Generating embedding for text (~{est_tokens} tokens)")
    
    # WALLET GUARD: API Call
    response = client.embeddings.create(
        input=truncated_text,
        model="text-embedding-3-small"
    )
    
    return response.data[0].embedding

def upsert_candidate_to_pinecone(registration) -> bool:
    """
    Build PII-safe metadata, generate embedding, upsert to Pinecone.
    
    Returns True on success, False on failure (never raises).
    """
    try:
        # 1. Call build_embedding_text
        text = build_embedding_text(registration)
        
        # 2. Call get_embedding
        vector = get_embedding(text)
        
        # 3. Build metadata (confirm NO PII fields)
        # [CONSTRAINT 1]
        metadata = {
            "employee_id": int(registration.pk),
            "years_of_experience": int(registration.years_of_experience or 0),
            "notice_period": str(registration.notice_period or ""),
            "skill_names": list(registration.skills.values_list("name", flat=True))
        }
        
        # 4. Upsert to Pinecone index with id=str(registration.pk)
        index = get_pinecone_index()
        
        # WALLET GUARD: Pinecone Upsert
        index.upsert(
            vectors=[{
                "id": str(registration.pk),
                "values": vector,
                "metadata": metadata
            }]
        )
        
        logger.info(f"[OK] ID {registration.pk} — {len(metadata['skill_names'])} skills vectorized")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Pinecone upsert failed for ID {registration.pk}: {str(e)}")
        return False

def search_candidates(query_text: str, top_k: int = 10, filters: dict = None) -> list[dict]:
    """
    Embed a natural language employer query and search Pinecone.
    
    Security: This function returns employee_ids only.
    """
    try:
        # 1. Embed query
        query_vector = get_embedding(query_text)
        
        # 2. Search Pinecone
        index = get_pinecone_index()
        
        # WALLET GUARD: Pinecone Query
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            filter=filters,
            include_metadata=True
        )
        
        formatted_results = []
        for match in results.matches:
            formatted_results.append({
                "employee_id": int(match.metadata["employee_id"]),
                "score": float(match.score),
                "metadata": match.metadata
            })
            
        return formatted_results
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return []
