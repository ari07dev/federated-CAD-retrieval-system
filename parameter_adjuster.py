import sys
from generation.cad_synthesis import generate_model

def adjust_parameters(model_type, new_spec):
    """
    Adjust parameters for a given model type.
    For this demo, we assume 'tank' type and regenerate.
    """
    print(f"Adjusting {model_type} with spec: {new_spec}")
    
    if "tank" in model_type.lower():
        result = generate_model(new_spec)
        print(f"New model generated: {result['file']}")
        return result
    else:
        print("Unknown model type for adjustment.")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python parameter_adjuster.py <type> <spec>")
        print("Example: python parameter_adjuster.py tank 500")
    else:
        adjust_parameters(sys.argv[1], sys.argv[2])
