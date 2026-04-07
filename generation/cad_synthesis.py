"""
Dynamic CAD Synthesis Engine
Uses Google Gemini (gemini-2.0-flash) to generate CadQuery code from natural language.
Includes retry logic with error feedback for robust generation.
Falls back to parametric box ONLY after all retries are exhausted.
"""
import cadquery as cq
import math
import os
import re
import uuid
import traceback

# Output directory
# Output directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATED_DIR = os.path.join(BASE_DIR, "static", "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)

# Maximum retry attempts when generated code fails
MAX_RETRIES = 3

# ---------- LLM-BASED GENERATION ----------


# Models to try in order (most capable → least capable)
MODEL_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def _call_gemini(query, error_feedback=None):
    """
    Calls Google Gemini to generate CadQuery Python code for the given query.
    If error_feedback is provided, asks the model to fix its previous code.
    Tries multiple models in case of quota/rate limits.
    Returns the generated code string, or None on failure.
    """
    import time
    from generation.llm_config import GOOGLE_API_KEY, CADQUERY_SYSTEM_PROMPT, GENERATION_PROMPT_TEMPLATE
    
    if not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set. Falling back to parametric box.")
        return None
    
    try:
        from google import genai
        
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        if error_feedback:
            prompt = (
                f"Your previous CadQuery code for \"{query}\" failed with this error:\n"
                f"```\n{error_feedback}\n```\n\n"
                f"Generate FIXED CadQuery Python code for: {query}\n\n"
                f"Fix the error above. Make sure the code is valid and produces a detailed model. "
                f"Store the final shape in `result`. `cq` and `math` are already available. "
                f"Return ONLY executable Python code, no markdown, no backticks."
            )
        else:
            prompt = GENERATION_PROMPT_TEMPLATE.format(query=query)
        
        # Try each model until one works
        last_error = None
        for model_name in MODEL_CHAIN:
            try:
                print(f"Trying model: {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "system_instruction": CADQUERY_SYSTEM_PROMPT,
                        "temperature": 0.2,
                    }
                )
                
                code = response.text.strip()
                
                # Clean up markdown code fences if LLM included them
                if code.startswith("```"):
                    lines = code.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    code = "\n".join(lines)
                
                # Remove any import lines the LLM might add
                code_lines = code.split("\n")
                code_lines = [l for l in code_lines if not re.match(r'^\s*(import\s+cadquery|from\s+cadquery|import\s+cq|import\s+math)', l)]
                code = "\n".join(code_lines)
                
                print(f"{model_name} generated {len(code)} chars of CadQuery code")
                return code
                
            except Exception as model_err:
                last_error = model_err
                print(f"{model_name} failed: {model_err}")
                time.sleep(1)  # Brief pause before trying next model
                continue
        
        print(f"All models failed. Last error: {last_error}")
        return None
        
    except Exception as e:
        print(f"Gemini setup error: {e}")
        traceback.print_exc()
        return None


def _execute_cadquery_code(code):
    """
    Safely executes LLM-generated CadQuery code in a restricted namespace.
    Returns (result, None) on success, or (None, error_string) on failure.
    """
    # Expanded namespace — includes math and common builtins the LLM might use
    namespace = {"cq": cq, "math": math, "__builtins__": {
        "range": range,
        "len": len,
        "int": int,
        "float": float,
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "enumerate": enumerate,
        "zip": zip,
        "list": list,
        "tuple": tuple,
        "dict": dict,
        "set": set,
        "str": str,
        "bool": bool,
        "sum": sum,
        "sorted": sorted,
        "reversed": reversed,
        "map": map,
        "filter": filter,
        "isinstance": isinstance,
        "type": type,
        "True": True,
        "False": False,
        "None": None,
        "print": lambda *a, **kw: None,  # no-op print
    }}
    
    try:
        exec(code, namespace)
        
        result = namespace.get("result")
        if result is None:
            return None, "Generated code did not produce a 'result' variable"
            
        return result, None
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"CadQuery execution error: {error_msg}")
        traceback.print_exc()
        return None, error_msg


def _svg_to_pdf(svg_path, pdf_path):
    """
    Converts an SVG file to a PDF using svglib + reportlab.
    """
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF

    drawing = svg2rlg(svg_path)
    if drawing is None:
        raise RuntimeError(f"Failed to parse SVG: {svg_path}")
    renderPDF.drawToFile(drawing, pdf_path, fmt="PDF")


def _export_result(result, label):
    """
    Exports a CadQuery result to a PDF technical drawing.
    Renders a 2D SVG projection, then converts to PDF.
    """
    filename = f"{label}_{uuid.uuid4().hex[:8]}.pdf"
    path = os.path.join(GENERATED_DIR, filename)

    # Step 1: Export as SVG (2D projection)
    svg_path = path.replace(".pdf", ".svg")
    cq.exporters.export(result, svg_path, exportType="SVG")

    # Step 2: Convert SVG → PDF
    _svg_to_pdf(svg_path, path)

    # Step 3: Clean up intermediate SVG
    try:
        os.remove(svg_path)
    except OSError:
        pass

    return {
        "file": f"generated/{filename}",
        "name": f"Generated: {label.replace('_', ' ').title()}",
        "description": f"AI-generated CAD drawing created by CadQuery from natural language query.",
        "generated": True,
        "type": "generated",
        "score": 1.0
    }


# ---------- FALLBACK GENERATOR ----------

def _generate_fallback_box(query):
    """
    Generates a simple parametric box as fallback when LLM is unavailable or fails
    after all retries.
    """
    nums = re.findall(r"(\d+)", query)
    size = float(nums[0]) if nums else 50.0
    size = max(20.0, min(size, 500.0))  # Clamp
    
    result = (
        cq.Workplane("XY")
        .box(size, size * 0.6, size * 0.4)
        .edges("|Z")
        .fillet(size * 0.05)
    )
    
    # Add a hole for some visual interest
    result = (
        result
        .faces(">Z")
        .workplane()
        .circle(size * 0.15)
        .cutThruAll()
    )
    
    label = query.strip().split()[0] if query.strip() else "part"
    label = re.sub(r'[^\w]', '_', label).lower()
    
    return _export_result(result, label)


# ---------- MAIN ENTRY POINT ----------

def generate_model(query):
    """
    Generates a CAD drawing (PDF) from a natural language query.
    
    Flow:
    1. Call Gemini LLM to generate CadQuery code
    2. Execute the code safely
    3. If execution fails, retry up to MAX_RETRIES times with error feedback
    4. Export to PDF (via SVG projection)
    5. If ALL retries fail → fallback to parametric box
    """
    print(f"\n{'='*60}")
    print(f"CAD GENERATION: '{query}'")
    print(f"{'='*60}")
    
    # Clean up label for filename
    label = query.strip().split()[0] if query.strip() else "part"
    label = re.sub(r'[^\w]', '_', label).lower()
    
    error_feedback = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n--- Attempt {attempt}/{MAX_RETRIES} ---")
        
        # Step 1: Generate code (with error feedback on retries)
        code = _call_gemini(query, error_feedback=error_feedback)
        
        if not code:
            print("No code returned from Gemini")
            break  # API failure — no point retrying
        
        print(f"--- Generated Code (first 800 chars) ---")
        print(code[:800])
        print(f"--- End Code ---")
        
        # Step 2: Execute
        result, error = _execute_cadquery_code(code)
        
        if result is not None:
            try:
                # Step 3: Export
                info = _export_result(result, label)
                print(f"\nSUCCESS on attempt {attempt}: Generated {info['file']}")
                
                # Enhance description with the query
                info["description"] = f"AI-generated 3D model of '{query}' created by CadQuery."
                info["name"] = f"Generated: {query.title()}"
                return info
                
            except Exception as e:
                print(f"Export failed: {e}")
                error_feedback = f"Export error: {e}"
        else:
            # Code execution failed — set up error feedback for retry
            error_feedback = f"Code:\n{code[:500]}\n\nError: {error}"
            print(f"Execution failed, will retry with error feedback...")
    
    # All retries exhausted
    print(f"\nAll {MAX_RETRIES} attempts failed. Falling back to parametric box...")
    return _generate_fallback_box(query)


if __name__ == "__main__":
    # Quick test with multiple queries
    test_queries = ["chemical reactor with inlet and outlet nozzles"]
    for q in test_queries:
        print(f"\n{'#'*60}")
        print(f"TESTING: {q}")
        print(f"{'#'*60}")
        result = generate_model(q)
        print(f"Result: {result}")
