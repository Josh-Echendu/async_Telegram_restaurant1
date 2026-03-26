import json
import orjson
import timeit

data = {
    "name": "John",
    "age": 30,
    "city": "New York",
    "details": [{"id": i, "value": f"value-{i}"} for i in range(1000)] # Added more data to make time measurement meaningful
}

# Use a lambda function to pass the code to timeit.timeit
# 'number' specifies how many times to execute the statement
json_time = timeit.timeit(lambda: json.dumps(data), number=100)
orjson_time = timeit.timeit(lambda: orjson.dumps(data), number=100)

print(f"json.dumps time (100 runs): {json_time} seconds")
print(f"orjson.dumps time (100 runs): {orjson_time} seconds")

# Optional: print the results from the original snippet to see output format
json_bytes = orjson.dumps(data).decode('utf-8')
print(f"\norjson output (decoded): {json_bytes[:50]}...")
json_str = json.dumps(data)
print(f"json output (string): {json_str[:50]}...")
