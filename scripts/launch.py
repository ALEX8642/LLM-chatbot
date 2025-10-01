#!/usr/bin/env python3
import subprocess
import time
import requests
import os
from dotenv import load_dotenv

# Model configuration
LOCAL_MODEL = "command-r7b"
CLOUD_MODEL = "gpt-oss-120b-cloud"
EVAL_MODEL = "mistral7b"
model_name = LOCAL_MODEL  # Change this to switch globally

load_dotenv()  # Load environment variables from .env file
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

gpu_log_path = os.path.expanduser("~/.ollama/gpu.log")  # Path to Ollama GPU log file

def run_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"✅ Success: {command}")
        print(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {command}")
        print(e.stderr)
        return ""

def wait_for_service(name, url, retries=10, delay=3):
    print(f"⏳ Waiting for {name} to be ready...")
    for i in range(retries):
        try:
            response = requests.get(url, timeout=2)
            if response.ok and response.content:
                print(f"✅ {name} is running")
                return True
        except requests.exceptions.RequestException:
            print(f"🔄 Attempt {i+1}: {name} not ready yet...")
        time.sleep(delay)
    print(f"❌ {name} did not respond after {retries * delay} seconds")
    return False

def wait_for_ollama(retries=10, delay=3):
    print("⏳ Waiting for Ollama to be ready...")
    for i in range(retries):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.ok and "models" in response.json():
                print("✅ Ollama is running")
                return True
        except requests.exceptions.RequestException:
            print(f"🔄 Attempt {i+1}: Ollama not ready yet...")
        time.sleep(delay)
    print(f"❌ Ollama did not respond after {retries * delay} seconds")
    return False

def stop_ollama():
    print("🛑 Stopping any running Ollama processes...")
    subprocess.run("pkill -x ollama", shell=True)
    time.sleep(2)

def start_ollama_with_logging():
    print("🚀 Starting Ollama with log redirection...")
    os.makedirs(os.path.dirname(gpu_log_path), exist_ok=True)
    open(gpu_log_path, "w").close()  # Clear old log
    subprocess.Popen(f"ollama serve > {gpu_log_path} 2>&1 &", shell=True)
    time.sleep(3)

def check_gpu_status_from_log(timeout=10):
    print("🔍 Waiting for GPU status in Ollama log...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with open(gpu_log_path, "r") as log:
                for line in log:
                    if "inference compute" in line.lower():
                        if 'name="' in line:
                            gpu_name = line.split('name="')[1].split('"')[0]
                            print(f"✅ GPU detected and in use: {gpu_name}")
                        else:
                            print("✅ GPU detected (name not found in log line).")
                        return
                    if "no compatible GPUs" in line.lower():
                        print("⚠️ No compatible GPU found for local models.")
                        return
        except Exception as e:
            print(f"❌ Could not read GPU log: {e}")
        time.sleep(1)
    print("ℹ️ GPU status unclear. Check Ollama output manually.")

def is_model_available(model_name):
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.ok:
            models = response.json().get("models", [])
            return any(model.get("name") == model_name for model in models)
    except requests.exceptions.RequestException:
        pass
    return False

def pull_model_if_missing(model_name):
    if is_model_available(model_name):
        print(f"✅ Model '{model_name}' is already available.")
    else:
        print(f"📦 Pulling model '{model_name}'...")
        result = subprocess.run(f"ollama pull {model_name}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"✅ Model '{model_name}' pulled successfully.")
        else:
            print(f"❌ Failed to pull model '{model_name}'")
            print(result.stderr)

def main():
    # Step 1: Start Docker services
    run_command("docker compose up -d")

    # Step 2: Stop Ollama and restart with GPU check
    stop_ollama()
    start_ollama_with_logging()
    if not model_name.endswith("-cloud"):
        check_gpu_status_from_log()

    # Step 3: Wait for services to be ready
    ollama_ready = wait_for_ollama()
    qdrant_ready = wait_for_service("Qdrant", "http://localhost:6333")
    opensearch_ready = wait_for_service("OpenSearch", "http://localhost:9200")

    # Step 4: Pull model if needed
    if ollama_ready:
        pull_model_if_missing(model_name)

    # Step 5: Launch chatbot
    if ollama_ready and qdrant_ready and opensearch_ready:
        print("🎉 All services are up! You can now start the backend and frontend.")
    else:
        print("🚫 Startup failed. Check logs and try again.")

if __name__ == "__main__":
    main()
