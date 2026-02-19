import os
import numpy as np
from colbert.infra import ColBERTConfig
from colbert.modeling.checkpoint import Checkpoint


class ColBERT:
    def __init__(self, name, **kwargs) -> None:
        print("ColBERT: Loading model", name)
        self.device = "cpu"

        DOCKER = kwargs.get("env") == "docker"
        if DOCKER:
            # This is a workaround for the issue with the docker container
            # where the torch extension is not loaded properly
            # and the following error is thrown:
            # /root/.cache/torch_extensions/py311_cpu/segmented_maxsim_cpp/segmented_maxsim_cpp.so: cannot open shared object file: No such file or directory

            lock_file = (
                "/root/.cache/torch_extensions/py311_cpu/segmented_maxsim_cpp/lock"
            )
            if os.path.exists(lock_file):
                os.remove(lock_file)

        self.ckpt = Checkpoint(
            name,
            colbert_config=ColBERTConfig(model_name=name),
        ).to(self.device)
        pass

    def calculate_similarity_scores(self, query_embeddings, document_embeddings):

        query_embeddings = query_embeddings.to(self.device)
        document_embeddings = document_embeddings.to(self.device)

        # Validate dimensions to ensure compatibility
        if query_embeddings.dim() != 3:
            raise ValueError(
                f"Expected query embeddings to have 3 dimensions, but got {query_embeddings.dim()}."
            )
        if document_embeddings.dim() != 3:
            raise ValueError(
                f"Expected document embeddings to have 3 dimensions, but got {document_embeddings.dim()}."
            )
        if query_embeddings.size(0) not in [1, document_embeddings.size(0)]:
            raise ValueError(
                "There should be either one query or queries equal to the number of documents."
            )

        # query_embeddings: (B, Q, D)
        # document_embeddings: (B, T, D)

        transposed_query_embeddings = np.transpose(query_embeddings, (0, 2, 1))

        computed_scores = np.matmul(document_embeddings, transposed_query_embeddings)
        # (B, T, Q)

        maximum_scores = computed_scores.max(axis=1)
        # (B, Q)

        final_scores = maximum_scores.sum(axis=1)
        # (B,)

        exp_scores = np.exp(final_scores - final_scores.max())
        normalized_scores = exp_scores / exp_scores.sum()

        return normalized_scores.detach().cpu().numpy().astype(np.float32)

    def predict(self, sentences):

        query = sentences[0][0]
        docs = [i[1] for i in sentences]

        # Embedding the documents
        embedded_docs = self.ckpt.docFromText(docs, bsize=32)[0]
        # Embedding the queries
        embedded_queries = self.ckpt.queryFromText([query], bsize=32)
        embedded_query = embedded_queries[0]

        # Calculate retrieval scores for the query against all documents
        scores = self.calculate_similarity_scores(
            embedded_query.unsqueeze(0), embedded_docs
        )

        return scores
