users = [{"name": "Alice", "role": "user"}, {"name": "Bob", "role": "admin"}]

# Get the first admin found, or None if no admin exists
first_admin = next((u for u in users if u["role"] == "admin"), None)
print(first_admin)  # Output: {'name': 'Bob', 'role': 'admin'}


numbers = [10, 20]

# turn the list into an iterator object
my_iterator = iter(numbers)

print(next(my_iterator))
print(next(my_iterator))
