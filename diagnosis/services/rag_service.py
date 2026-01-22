"""
RAG Service - Handles embeddings, FAISS indexing, and retrieval
"""
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer
from pathlib import Path
from django.conf import settings

class RAGService:
    """Service for RAG operations: embedding, indexing, and retrieval"""
    
    def __init__(self):
        """Initialize the RAG service with sentence transformer model"""
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dimensional embeddings
        self.embedding_dim = 384
        self.index = None
        self.case_ids = []
        self.index_path = Path(settings.BASE_DIR) / 'faiss_index'
        self.index_path.mkdir(exist_ok=True)
        
    def generate_embedding(self, text):
        """
        Generate embedding for given text
        
        Args:
            text (str): Text to embed
            
        Returns:
            numpy.ndarray: Embedding vector
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding
    
    def numpy_to_binary(self, arr):
        """Convert numpy array to binary for database storage"""
        return pickle.dumps(arr)
    
    def binary_to_numpy(self, binary_data):
        """Convert binary data to numpy array"""
        return pickle.loads(binary_data)
    
    def build_index(self, knowledge_cases):
        """
        Build FAISS index from knowledge cases
        
        Args:
            knowledge_cases: QuerySet of KnowledgeCase objects
        """
        if not knowledge_cases.exists():
            print("No knowledge cases to index")
            return
        
        # Collect embeddings and case IDs
        embeddings_list = []
        self.case_ids = []
        
        for case in knowledge_cases:
            if case.embedding:
                embedding = self.binary_to_numpy(case.embedding)
                embeddings_list.append(embedding)
                self.case_ids.append(case.case_id)
        
        if not embeddings_list:
            print("No embeddings found in knowledge cases")
            return
        
        # Convert to numpy array
        embeddings = np.array(embeddings_list).astype('float32')
        
        # Create FAISS index
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        self.index.add(embeddings)
        
        # Save index and case IDs
        faiss.write_index(self.index, str(self.index_path / 'knowledge_base.index'))
        with open(self.index_path / 'case_ids.pkl', 'wb') as f:
            pickle.dump(self.case_ids, f)
        
        print(f"FAISS index built with {len(embeddings_list)} cases")
    
    def load_index(self):
        """Load FAISS index from disk"""
        index_file = self.index_path / 'knowledge_base.index'
        case_ids_file = self.index_path / 'case_ids.pkl'
        
        if index_file.exists() and case_ids_file.exists():
            self.index = faiss.read_index(str(index_file))
            with open(case_ids_file, 'rb') as f:
                self.case_ids = pickle.load(f)
            print(f"FAISS index loaded with {len(self.case_ids)} cases")
            return True
        else:
            print("No existing index found")
            return False
    
    def retrieve_similar_cases(self, query_embedding, k=5):
        """
        Retrieve top-K similar cases using FAISS
        
        Args:
            query_embedding: Embedding vector of the query
            k: Number of similar cases to retrieve
            
        Returns:
            list: List of case IDs for similar cases
        """
        if self.index is None:
            # Try to load existing index
            if not self.load_index():
                print("No index available for retrieval")
                return []
        
        if self.index.ntotal == 0:
            print("Index is empty")
            return []
        
        # Ensure query embedding is the right shape
        query_embedding = np.array([query_embedding]).astype('float32')
        
        # Search for similar cases
        distances, indices = self.index.search(query_embedding, min(k, self.index.ntotal))
        
        # Get case IDs
        retrieved_case_ids = [self.case_ids[idx] for idx in indices[0]]
        
        return retrieved_case_ids
    
    def get_or_build_index(self, force_rebuild=False):
        """
        Get existing index or build new one
        
        Args:
            force_rebuild: Force rebuild even if index exists
        """
        if force_rebuild or not self.load_index():
            from diagnosis.models import KnowledgeCase
            knowledge_cases = KnowledgeCase.objects.all()
            self.build_index(knowledge_cases)
