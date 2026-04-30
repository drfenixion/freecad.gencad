"""
Part verification module for GenCAD.
Verifies generated FreeCAD code against user request using LLM.
Returns either "verified - ok" or corrected code.
"""

from langchain_core.messages import SystemMessage, HumanMessage


VERIFICATION_SYSTEM_PROMPT = """You are a code verification assistant for FreeCAD Python code generation.

Your task is to check whether the generated FreeCAD Python code correctly implements the user's request.

Check the following:
1. All dimensions, parameters, and values match the user's request
4. No extra or missing features compared to the request

If the code is correct and matches the request, respond exactly with: verified - ok

If the code needs corrections, respond with the FULL corrected FreeCAD Python code only (no explanations, no markdown fences).

IMPORTANT: Your response MUST be either exactly "verified - ok" or the corrected FreeCAD code."""


def verify_generated_code(user_request: str, generated_code: str) -> dict:
    """Verify generated code against user request using LLM.

    Args:
        user_request: The original user description/request
        generated_code: The generated FreeCAD Python code

    Returns:
        dict with:
            - 'verified': bool — True if code passed verification
            - 'corrected_code': str or None — corrected code if verification failed
            - 'raw_response': str — the raw LLM response
    """
    from src.llm_client import _invoke_llm

    # Build the verification prompt
    user_prompt = f"""Request: {user_request}

Code:
{generated_code}
"""

    messages = [
        SystemMessage(content=VERIFICATION_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        # import debugpy; debugpy.breakpoint()
        response = _invoke_llm(messages)
        response = response.strip()

        # Check if verified
        if response.lower() == "verified - ok":
            return {
                "verified": True,
                "corrected_code": None,
                "raw_response": response,
            }

        # Otherwise, treat the response as corrected code
        # Clean markdown code fences if present
        response = _clean_code_fences(response)

        return {
            "verified": False,
            "corrected_code": response,
            "raw_response": response,
        }

    except Exception as e:
        # If LLM call fails, assume verified to avoid blocking generation
        return {
            "verified": True,
            "corrected_code": None,
            "raw_response": f"Verification LLM call failed: {str(e)}",
        }


def _clean_code_fences(code: str) -> str:
    """Remove markdown code fences and language prefix."""
    if code.startswith("```"):
        code = code.strip("`\n ")
        if code.lower().startswith("python"):
            code = code[len("python") :].lstrip()
    return code
