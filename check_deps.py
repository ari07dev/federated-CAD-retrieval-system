
try:
    import clip
    print("CLIP available")
except ImportError:
    print("CLIP missing")

try:
    import cadquery
    print("CadQuery available")
except ImportError:
    print("CadQuery missing")
