from scraper_module.expired import mark_expired_jobs
from scraper_module.scraper import JobScraper

A_CORE_BACKEND = [
    "python",
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "kafka",
    "activemq",
    "postgres",
    "postgresql",
    "mysql",
    "sql server",
    "alembic",
    "uvicorn",
    "asyncio",
    "async",
    "pytest",
    "celery",
    "gunicorn",
]

B_API_LAYER = [
    "django",
    "flask",
    "api",
    "rest",
    "rest api",
    "restful",
    "microservices",
    "graphql",
    "grpc",
    "openapi",
    "swagger",
    "websocket",
    "websockets",
    "event-driven",
    "event driven",
]

C_AI_ML = [
    "pandas",
    "numpy",
    "scipy",
    "matplotlib",
    "scikit-learn",
    "tensorflow",
    "keras",
    "pytorch",
    "machine learning",
    "deep learning",
    "nlp",
    "computer vision",
    "neural network",
    "data science",
    "artificial intelligence",
    "chatgpt",
    "llm",
    "large language model",
    "generative ai",
    "genai",
    "langchain",
    "langgraph",
    "rag",
    "retrieval augmented generation",
    "vector database",
    "vector search",
    "embedding",
    "embeddings",
    "hugging face",
    "transformers",
    "hitl",
    "human in the loop",
    "human-in-the-loop",
    "human feedback",
    "human review",
    "agent",
    "ai agent",
    "agents",
    "mcp",
    "model context protocol",
    "prompt engineering",
    "inference",
    "fine tuning",
    "fine-tuning",
]

D_BACKEND_ENV = [
    "docker",
    "aws",
    "azure",
    "gcp",
    "google cloud",
    "kubernetes",
    "terraform",
    "ci/cd",
    "continuous integration",
    "continuous delivery",
    "etl",
    "airflow",
    "spark",
    "polyglot",
    "redis",
    "rabbitmq",
    "azure functions",
    "lambda",
    "fargate",
    "ecs",
    "sqs",
    "sns",
    "service bus",
    "azure service bus",
    "mongodb",
    "elasticsearch",
    "opensearch",
]

E_FRONTEND = [
    "react",
    "javascript",
    "typescript",
]

F_EXCLUDE = [
    "java",
    "spring",
    "spring boot",
    "c#",
    "asp.net",
    ".net",
    ".net core",
    "android",
    "kotlin",
]

G_ROLE = [
    "software engineer",
    "software developer",
    "backend",
    "backend engineer",
    "programmer",
    "frontend",
    "full stack",
    "python developer",
    "python engineer",
    "platform engineer",
    "application developer",
    "application engineer",
]

H_LANG = [
    "rust",
    "C++",
]

SEARCH_TERMS = (
    A_CORE_BACKEND
    + B_API_LAYER
    + C_AI_ML
    + D_BACKEND_ENV
    + E_FRONTEND
    + F_EXCLUDE
    + G_ROLE
    + H_LANG
)


search_terms = [f"{s}" for s in SEARCH_TERMS]


def main():
    scraper = JobScraper(load_network_handler=True)
    mark_expired_jobs(scraper)
    scraper.perform_searches(search_terms)

    print("Finished scraping.\n")


if __name__ == "__main__":
    main()
