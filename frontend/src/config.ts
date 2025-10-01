// Environment configuration
export const config = {
    // API endpoints
    BACKEND_BASE: import.meta.env.VITE_BACKEND_URL || "http://localhost:8000",
    
    // PDF paths
    MANUALS_PATH: "/manuals",  // Relative to public directory
    
    // Service endpoints
    QDRANT_URL: "http://localhost:6333",
    OPENSEARCH_URL: "http://localhost:9200",
    OLLAMA_URL: "http://localhost:11434"
} as const;