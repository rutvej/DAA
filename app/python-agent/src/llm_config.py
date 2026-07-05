import os
import logging

def get_llm():
    """
    Returns a LangChain chat model based on environment configuration.
    Supports Google Gemini, OpenAI, and Ollama/local models.
    """
    provider = os.environ.get("LLM_PROVIDER", "google").lower()
    model_name = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")

    logging.info(f"Initializing LLM: provider={provider}, model={model_name}, base_url={base_url}")

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        m = model_name or "gemini-2.5-flash"
        return ChatGoogleGenerativeAI(model=m, google_api_key=api_key)
    
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        m = model_name or "gpt-4o"
        return ChatOpenAI(model=m, openai_api_key=api_key, base_url=base_url)
    
    elif provider in ("ollama", "local"):
        from langchain_openai import ChatOpenAI
        m = model_name or "llama3"
        url = base_url or "http://localhost:11434/v1"
        return ChatOpenAI(model=m, openai_api_key=api_key or "ollama", base_url=url)
    
    else:
        # Fallback to Google Gemini
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
