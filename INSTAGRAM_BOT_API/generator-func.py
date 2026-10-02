# A function is NOT an iterable UNTIL it has yield inside it.

# When a function has yield, it becomes a GENERATOR, and generators ARE iterables!

def generator_function():
    yield "Hello"
    yield "World"


# This WORKS:
gen = generator_function()  # ← gen is a GENERATOR object
print("genarator_function: ", type(gen)) # <class 'generator'>
print(next(gen))  # ✅ "Hello"
print(next(gen))  # ✅ "World"

def ab():
    return [1, 2, 3]

func = ab()
print("ab: ", type(func)) # <class 'list'>


def regular_function():
    yield [1, 2, 3]
    yield [3, 2, 1]
    yield [5, 4, 3]

# This WON'T work:
gen = regular_function()
print("regular_function: ", type(gen)) # <class 'generator'>
print(next(gen))
print(next(gen))
print(next(gen))

# 3. You can even use it in a for loop
for value in regular_function():  # ✅ Works!
    print("iterable:", value)
# Output: 1, 2

# 4. Convert to list
print("convert to a list of list :", list(regular_function()))  # ✅ [1, 2]

# Regular Function (NOT iterable):
# Why? regular_function() returns a string, not an iterable.
def regular_function():
    return "Hello"


# This WON'T work:
regular = regular_function()
print(type(regular)) # <class 'str'>
next(regular_function())  # ❌ TypeError: 'str' object is not an iterator