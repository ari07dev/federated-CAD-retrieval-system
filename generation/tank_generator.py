def generate_tank(capacity_liters):
    radius = (capacity_liters / 3.14) ** 0.5
    height = radius * 2
    return {
        "type": "Generated Tank",
        "capacity": capacity_liters,
        "radius": round(radius, 2),
        "height": round(height, 2)
    }
