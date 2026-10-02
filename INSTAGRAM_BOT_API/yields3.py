from contextlib import contextmanager

def pizza_oven():
    try:
        print("🔥 Starting...")
        yield "Pizza 1"  # ← PAUSE, SEND DATA
        print("🍕 Delivered 1")
        yield "Pizza 2"  # ← PAUSE, SEND DATA

    finally:

        # insert in a finally block so after yield return it is executed
        print("🍕 Delivered 2")

oven = pizza_oven()
pizza1 = next(oven)  # Runs to first yield, gets "Pizza 1"
print(pizza1)
pizza2 = next(oven)  # Resumes, runs to second yield, gets "Pizza 2"
print(pizza2)

@contextmanager
def context_pizza_oven():
    try:
        print("🔥 Starting...")
        yield "Pizza 1"  # ← PAUSE, SEND DATA
        print("🍕 Delivered 1")
        
    finally:
        print("🍕 Delivered 2")
        
with context_pizza_oven() as oven:
    print(oven)
