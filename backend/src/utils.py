import json
import time
import numpy as np

def format_results(results):
    # Format the results for better readability
    formatted = {
        "average_lifetime": np.mean(results["lifetime"]),
        "total_energy": np.sum(results["energy"]),
        "alive_nodes": np.mean(results["alive"]),
    }
    return formatted

def log_message(message):
    # Simple logging function to print messages with a timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] {message}")

def save_results_to_file(results, filename):
    # Save the results to a JSON file
    with open(filename, 'w') as f:
        json.dump(results, f)

def load_results_from_file(filename):
    # Load results from a JSON file
    with open(filename, 'r') as f:
        return json.load(f)