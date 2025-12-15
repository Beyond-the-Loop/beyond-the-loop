from beyond_the_loop.config import VECTOR_DB

if VECTOR_DB == "pgvector":
    from beyond_the_loop.retrieval.vector.dbs.pgvector import PgvectorClient

    VECTOR_DB_CLIENT = PgvectorClient()
else:
    from beyond_the_loop.retrieval.vector.dbs.chroma import ChromaClient

    VECTOR_DB_CLIENT = ChromaClient()