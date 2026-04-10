from scraper_module.scraper import JobScraper, LinkStatus
from scraper_module.expired import mark_expired_jobs


A_CORE_BACKEND = [
    "python",
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "kafka",
    "activemq",
    "postgres",
    "mysql",
    "sql server",
    "alembic",
    "uvicorn",
]

B_API_LAYER = [
    "django",
    "flask",
    "api",
    "rest",
    "microservices",
    "graphql",
    "grpc",
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
    "langchain",
]

D_BACKEND_ENV = [
    "docker",
    "aws",
    "kubernetes",
    "terraform",
    "ci/cd",
    "etl",
    "airflow",
    "spark",
    "polyglot",
    "redis",
    "rabbitmq",
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
    "programmer",
]


H_LANG = [
    "rust",
    "C++",
]


SEARCH_TERMS = (
    A_CORE_BACKEND +
    B_API_LAYER +
    C_AI_ML +
    D_BACKEND_ENV +
    E_FRONTEND +
    F_EXCLUDE +
    G_ROLE +
    H_LANG
)


search_terms = [f"{s}" for s in SEARCH_TERMS]


if __name__ == "__main__":
    scraper = JobScraper(load_network_handler=True)
    mark_expired_jobs(scraper)
    scraper.perform_searches(search_terms)
    
    print("Finished scraping.\n")
