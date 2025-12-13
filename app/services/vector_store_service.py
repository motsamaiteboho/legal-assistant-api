from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from app.config.config import Config

class VectorStoreService:
    """Service for managing vector store operations"""
    
    def __init__(self):
        self.embeddings = None
        self.vectorstore = None
        self.retriever = None
        self.multi_retriever = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize vector store and retrievers"""
        try:
            self.embeddings = OpenAIEmbeddings(model=Config.EMBEDDING_MODEL)
            self.vectorstore = FAISS.load_local(
                Config.FAISS_INDEX_PATH,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
            print("✅ Vector store services initialized successfully!")
        except Exception as e:
            print(f"❌ Failed to initialize vector store: {e}")
            self.vectorstore = None
            self.retriever = None
    
    def is_available(self):
        """Check if vector store is available"""
        return self.vectorstore is not None
    
    def get_retriever(self, use_multi_query=True):
        """Get the appropriate retriever"""
        if not self.is_available():
            return None
        
        if use_multi_query and hasattr(self, 'multi_retriever'):
            return self.multi_retriever
        return self.retriever

# Global instance
vector_store_service = VectorStoreService()