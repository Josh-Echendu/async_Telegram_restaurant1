from contextlib import contextmanager

@contextmanager
def my_resource():
    print("🔓 Opening...")
    yield "lime stone"  # ← PAUSE, RUN `with` BLOCK
    print("🔒 Closing...")

with my_resource() as resource:
    print(f"Using: {resource}")  # ← Runs during the pause


numbers = [10, 20, 30]
my_iterator = iter(numbers)

print(next(my_iterator))  # Output: 10
print(next(my_iterator))  # Output: 20
print(next(my_iterator))  # Output: 30
# print(next(my_iterator)) # This would raise StopIteration
