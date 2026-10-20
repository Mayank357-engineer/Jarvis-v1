import json
import os


MEMORY_FILE = "memory.json"


def remember_fact(key, value):
    # Create memory file if it does not exist
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            memory = json.load(file)
    else:
        memory = {}

    # Save or update the memory
    memory[key] = value

    # Write memory back to file
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memory, file, indent=4, ensure_ascii=False)

    return f"I'll remember that {key} is {value}."

#--------------recall function -----------------------------

def recall_memory(key):
    if not os.path.exists(MEMORY_FILE):
        return "I don't have any saved memories yet."

    with open(MEMORY_FILE, "r", encoding="utf-8") as file:
        memory = json.load(file)

    if key in memory:
        return memory[key]

    return "I don't remember that."