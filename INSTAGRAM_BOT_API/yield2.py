# generator_yield.py
def pizza_oven():
    print("🔥 Oven starting...")
    
    for i in range(1, 4):
        print(f"🍕 Baking pizza #{i}...")
        yield f"Pizza #{i} is ready!"  # ← PAUSE, SEND DATA
        print(f"🍕 Pizza #{i} delivered!")

# Using the generator
oven = pizza_oven()  # Nothing happens yet!

print("--- Getting pizza 1 ---")
pizza1 = next(oven)  # Runs until first yield
print(f"Got: {pizza1}")

print("\n--- Getting pizza 2 ---")
pizza2 = next(oven)  # Resumes from after first yield
print(f"Got: {pizza2}")

print("\n--- Getting pizza 3 ---")
pizza3 = next(oven)  # Resumes from after second yield
print(f"Got: {pizza3}")

print("\n--- Getting pizza 4 ---")
try:
    pizza4 = next(oven)  # Function ends, raises StopIteration
    print(f"Got: {pizza4}")
except StopIteration:
    print("No more pizzas!")