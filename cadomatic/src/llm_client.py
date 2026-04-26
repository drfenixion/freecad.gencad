from cadomatic.src.dependency_checker import add_freecad_python_paths


add_freecad_python_paths()


import os
import sys
import uuid
import FreeCAD
import requests
from pathlib import Path

# Suppress HFace and Transformers warnings/progress bars
# os.environ.setdefault("HF_HUB_VERBOSITY", "error")
# os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
# os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

from huggingface_hub import hf_hub_download
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from src.load_environment import load_env

GEMINI_API_KEY = load_env.GEMINI_API_KEY
USE_OLLAMA = load_env.USE_OLLAMA
USE_OPENROUTER = getattr(load_env, 'USE_OPENROUTER', False)  # New option for Qwen3 via OpenRouter
USE_ROUTERAIRU = getattr(load_env, 'USE_ROUTERAIRU', False)  # New option for ROUTERAIRU
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'gpt-oss:120b-cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'qwen3-vl:235b-instruct-cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'qwen3-coder-next:cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'kimi-k2.5:cloud') # too bad
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'qwen3-next:80b-cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'deepseek-v3.1:671b-cloud')
OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'gemini-3-flash-preview:cloud') # good
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'glm-5:cloud') # good
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'glm-4.7:cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'devstral-2:123b-cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'cogito-2.1:671b-cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'rnj-1:8b-cloud') # too bad
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'ministral-3:14b-cloud') # too bad
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'nemotron-3-nano:30b-cloud') # too bad
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'minimax-m2:cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'deepseek-v3.2:cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'mistral-large-3:675b-cloud')
# OLLAMA_MODEL = getattr(load_env, 'OLLAMA_MODEL', 'gemma3:27b-cloud') # bad (small limit on prompt)


RAG_retriever = None

def _load_config():
    """Load GenCAD configuration from file."""
    import json
    from pathlib import Path
    
    config_dir = Path.home() / '.freecad' / 'GenCAD'
    config_file = config_dir / 'config.json'
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def convert_langchain_messages_to_dicts(messages):
    """Convert LangChain messages to dict format for API calls."""
    role_map = {
        SystemMessage: "system",
        HumanMessage: "user",
        AIMessage: "assistant",
    }
    converted = []
    for msg in messages:
        for msg_type, role in role_map.items():
            if isinstance(msg, msg_type):
                converted.append({"role": role, "content": msg.content})
                break
        else:
            converted.append(msg)
    return converted


def _reload_config():
    """Reload configuration from config file to get latest GUI settings."""
    load_env._load_gencad_config()
    load_env._apply_gencad_config()


def _validate_response_content(generated_code: str, api_name: str) -> str:
    """Validate that the API response is not empty."""
    if not generated_code:
        raise RuntimeError(
            f"{api_name} API response with empty content. "
            "It can be related to model setting (max response tokens limit) and those limit spent to think."
        )
    return generated_code


def call_openrouter_api(messages) -> str:
    """Call LLM via OpenRouter API to generate CAD code."""
    _reload_config()
    
    openrouter_api_key = getattr(load_env, 'OPENROUTER_API_KEY', '')
    openrouter_model = getattr(load_env, 'OPENROUTER_MODEL', 'google/gemini-3-flash-preview')

    if not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    payload = {
        "model": openrouter_model,
        "messages": convert_langchain_messages_to_dicts(messages),
        "temperature": 0.2,
        "max_tokens": 2048,
        "provider": {
            "allow_fallbacks": False,
            "order": [],
            "ignore": []
        },
        "cache": {
            "control": {"no_store": True}
        }
    }

    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "",
        "X-Title": "",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            generated_code = result["choices"][0]["message"]["content"]
            _validate_response_content(generated_code, "OpenRouter")
            FreeCAD.Console.PrintMessage("Successfully generated CAD code using OpenRouter API\n")
            return generated_code
        else:
            raise RuntimeError(f"OpenRouter API request failed with status {response.status_code}: {response.text}")

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error when calling OpenRouter API: {str(e)}")


def call_routerairu_api(messages) -> str:
    """Call LLM via ROUTERAIRU API to generate CAD code."""
    from openai import OpenAI
    
    _reload_config()
    
    routerairu_api_key = getattr(load_env, 'ROUTERAIRU_API_KEY', '')
    routerairu_model = getattr(load_env, 'ROUTERAIRU_MODEL', 'google/gemini-3-flash-preview')

    if not routerairu_api_key:
        raise ValueError("ROUTERAIRU_API_KEY not set in environment")

    client = OpenAI(
        api_key=routerairu_api_key,
        base_url="https://routerai.ru/api/v1"
    )

    extra_body = {
        "thinking_config": {"thinking_budget": 0},
        "chat_template_kwargs": {"enable_thinking": False},
        "enable_thinking": False,
        "cache_control": {"type": "ephemeral"},
        "stream_options": {"include_usage": False},
        "reasoning_effort": "low" if routerairu_model.startswith("openai/") else "none",
    }

    try:
        response = client.chat.completions.create(
            model=routerairu_model,
            messages=convert_langchain_messages_to_dicts(messages),
            extra_body=extra_body
        )

        generated_code = response.choices[0].message.content
        _validate_response_content(generated_code, "ROUTERAIRU")
        
        FreeCAD.Console.PrintMessage("Successfully generated CAD code using ROUTERAIRU API\n")
        return generated_code

    except Exception as e:
        raise RuntimeError(f"Error calling ROUTERAIRU API: {str(e)}")


workflow = StateGraph(state_schema=MessagesState)

# Lazy-initialized Ollama LLM instance
_ollama_llm = None


def _get_ollama_llm():
    """Get or create Ollama LLM instance with current model from config."""
    global _ollama_llm
    if _ollama_llm is None:
        from langchain_ollama import ChatOllama
        # Reload config to get latest model setting
        _reload_config()
        current_model = getattr(load_env, 'OLLAMA_MODEL', OLLAMA_MODEL)
        _ollama_llm = ChatOllama(
            model=current_model,
            base_url="http://localhost:11434",
            validate_model_on_init=True,
            temperature=0.1,
        )
    return _ollama_llm


# Determine initial LLM for backward compatibility
if USE_OPENROUTER:
    llm = "openrouter_api"
elif USE_OLLAMA:
    llm = "ollama_api"
elif USE_ROUTERAIRU:
    llm = "routerairu_api"


def load_modeling_options_prompts():
    """Load modeling option prompts based on settings from config file."""
    import json
    from pathlib import Path
    
    options_prompts_dir = Path(__file__).parent.parent / "prompts" / "options"
    config_dir = Path.home() / '.freecad' / 'GenCAD'
    config_file = config_dir / 'config.json'
    
    # Load config
    config = {}
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    options_content = []
    
    # 1) Build Tree / Bake Part
    build_tree = config.get('build_tree', 'Build Tree of Part')
    if build_tree == 'Build Tree of Part':
        prompt_file = options_prompts_dir / "build_tree.txt"
    else:
        prompt_file = options_prompts_dir / "bake_part.txt"
    if prompt_file.exists():
        options_content.append(prompt_file.read_text().strip())
    
    # 2) Use Sketches / Use Primitives / Auto
    modeling_approach = config.get('modeling_approach', 'Use Sketches')
    if modeling_approach == 'Auto':
        # Load both prompts without the first line of each
        sketches_file = options_prompts_dir / "use_sketches.txt"
        primitives_file = options_prompts_dir / "use_primitives.txt"
        if sketches_file.exists():
            sketches_content = sketches_file.read_text().strip().split('\n', 1)
            sketches_content = sketches_content[1] if len(sketches_content) > 1 else ''
            options_content.append(sketches_content.strip())
        if primitives_file.exists():
            primitives_content = primitives_file.read_text().strip().split('\n', 1)
            primitives_content = primitives_content[1] if len(primitives_content) > 1 else ''
            options_content.append(primitives_content.strip())
        # Add specialized sketcher_and_primitives prompt
        sketcher_and_primitives_file = options_prompts_dir / "sketcher_and_primitives.txt"
        if sketcher_and_primitives_file.exists():
            options_content.append(sketcher_and_primitives_file.read_text().strip())
    elif modeling_approach == 'Use Sketches':
        prompt_file = options_prompts_dir / "use_sketches.txt"
        if prompt_file.exists():
            options_content.append(prompt_file.read_text().strip())
    else:
        prompt_file = options_prompts_dir / "use_primitives.txt"
        if prompt_file.exists():
            options_content.append(prompt_file.read_text().strip())
    
    # 3) PartDesign WB / Part WB
    workbench = config.get('workbench', 'Use PartDesign WB')
    if workbench == 'Use PartDesign WB':
        prompt_file = options_prompts_dir / "use_partdesign.txt"
    else:
        prompt_file = options_prompts_dir / "use_part.txt"
    if prompt_file.exists():
        options_content.append(prompt_file.read_text().strip())
    
    # 4) PolarPattern / Placement for circular placement
    circular_placement = config.get('circular_placement', 'Use PartDesign_PolarPattern')
    if circular_placement == 'Use PartDesign_PolarPattern':
        prompt_file = options_prompts_dir / "use_polarpattern.txt"
    else:
        prompt_file = options_prompts_dir / "use_placement_circle.txt"
    if prompt_file.exists():
        options_content.append(prompt_file.read_text().strip())

    # 5) Use Fasteners WB
    use_fasteners_wb = config.get('use_fasteners_wb', False)
    if use_fasteners_wb:
        prompt_file = options_prompts_dir / "use_fasteners_wb.txt"
        if prompt_file.exists():
            options_content.append(prompt_file.read_text().strip())

    return "\n\n".join(options_content)


def _build_system_content(last_user_message: str) -> str:
    """Build the system content with timestamp, prompts, and RAG context."""
    from datetime import datetime
    
    global RAG_retriever
    context = ""
    config = _load_config()
    use_rag = config.get('use_rag', False)
    if use_rag:
        if RAG_retriever is None:
            # ### REPO VECTORSTORE
            # REPO_ID = "hf_user/gencad_vectorstore"
            # FILENAME_FAISS = "index.faiss"
            # FILENAME_PKL = "index.pkl"

            # faiss_path = hf_hub_download(repo_id=REPO_ID, filename=FILENAME_FAISS)
            # pkl_path = hf_hub_download(repo_id=REPO_ID, filename=FILENAME_PKL)
            # vectorstore_dir = Path(faiss_path).parent    

            ### LOCAL VECTORSTORE
            # run rag_builder.py to make new data in local store
            vectorstore_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../vectorstore/final")

            embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            vectorstore = FAISS.load_local(
                str(vectorstore_dir),
                embeddings=embedding,
                allow_dangerous_deserialization=True,
                index_name="index"
            )
            
            RAG_retriever = vectorstore.as_retriever(search_kwargs={"k": 15})     

        docs = RAG_retriever.invoke(last_user_message)
        context = "\n\n".join(doc.page_content for doc in docs)
    
    base_instruction = Path(__file__).parent.parent / "prompts" / "base_instruction.txt"
    system_prompt = base_instruction.read_text().strip()
    options_prompt = load_modeling_options_prompts()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    if context:
        context = "Relevant FreeCAD documentation context: \n" + context
    return f"""Current time: {timestamp}

{system_prompt}

{options_prompt}

{context}"""


def _prepare_messages_with_system(state: MessagesState, system_content: str) -> list:
    """Prepare messages with system prompt, ensuring it's the first message."""
    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=system_content))
    return messages


def _invoke_llm(messages: list) -> str:
    """Invoke the appropriate LLM backend and return response content.
    
    Determines which LLM to use at runtime based on current configuration,
    so that provider changes in settings take effect immediately.
    """
    # Reload config to get latest provider and model settings
    _reload_config()
    
    # Determine which LLM to use based on current config
    current_use_ollama = getattr(load_env, 'USE_OLLAMA', False)
    current_use_openrouter = getattr(load_env, 'USE_OPENROUTER', False)
    current_use_routerairu = getattr(load_env, 'USE_ROUTERAIRU', False)
    
    if current_use_openrouter:
        return call_openrouter_api(messages)
    elif current_use_routerairu:
        return call_routerairu_api(messages)
    elif current_use_ollama:
        response = _get_ollama_llm().invoke(messages)
        return response.content
    else:
        raise ValueError("No LLM provider configured. Please select a provider in GenCAD settings.")


def call_model(state: MessagesState):
    """Generate FreeCAD Python code based on conversation state and RAG context."""
    last_user_message = state["messages"][-1].content
    system_content = _build_system_content(last_user_message)
    messages = _prepare_messages_with_system(state, system_content)
    
    response_content = _invoke_llm(messages)
    return {"messages": [AIMessage(content=response_content)]}

# Add nodes and edges to the graph
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# Unique conversation ID for session persistence
thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}


def _stream_llm_response(input_message: HumanMessage) -> str:
    """Stream LLM response and return the content."""
    response_text = ""
    for event in app.stream({"messages": [input_message]}, config, stream_mode="values"):
        response_text = event["messages"][-1].content
    return response_text


def prompt_llm(user_prompt: str) -> str:
    """Send a user prompt and get the model response while preserving conversation history."""
    return _stream_llm_response(HumanMessage(content=user_prompt))


def prompt_llm_with_context(full_prompt: str, user_request: str) -> str:
    """Send a prompt with context (e.g., existing code) and get the model response.
    
    Args:
        full_prompt: The full prompt including context and instructions
        user_request: The user's modification request (used for history tracking)
    
    Returns:
        str: Model response
    """
    return _stream_llm_response(HumanMessage(content=full_prompt))


def reset_memory():
    """Start a new conversation by resetting the thread ID."""
    global thread_id, config
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}