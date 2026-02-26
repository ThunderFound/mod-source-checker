import hashlib
import os
import requests
import json
import time
import struct
from dotenv import load_dotenv

load_dotenv()

def get_sha1(filename):
    h = hashlib.sha1()
    with open(filename, 'rb') as file:
        while chunk := file.read(8192):
            h.update(chunk)
    return h.hexdigest()

def get_curseforge_fingerprint(filename: str) -> int:
    multiplex = 1540483477
    
    with open(filename, 'rb') as f:
        data = f.read()

    normalized = data.translate(None, b'\x09\x0a\x0d\x20')
    length = len(normalized)
    
    if length == 0:
        return 0

    hash_val = 1 ^ length
    
    num_chunks = length // 4
    remainder = length % 4
    
    if num_chunks > 0:
        chunk_data = normalized[:num_chunks * 4]
        
        for (k,) in struct.iter_unpack('<I', chunk_data):
            k = (k * multiplex) & 0xFFFFFFFF
            k = ((k ^ (k >> 24)) * multiplex) & 0xFFFFFFFF
            hash_val = ((hash_val * multiplex) ^ k) & 0xFFFFFFFF
            
    if remainder > 0:
        buffer = int.from_bytes(normalized[-remainder:], byteorder='little')
        hash_val = ((hash_val ^ buffer) * multiplex) & 0xFFFFFFFF
        
    hash_val = ((hash_val ^ (hash_val >> 13)) * multiplex) & 0xFFFFFFFF
    hash_val = (hash_val ^ (hash_val >> 15)) & 0xFFFFFFFF
    
    return hash_val
    
def check_curseforge(session, filenames):
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-api-key': os.getenv("CURSEFORGE_API_KEY")
    }
    start = time.time()
    fingerprints = {filename: get_curseforge_fingerprint(filename) for filename in filenames}
    print(f"calculating fingerprints took {time.time() - start}s")
    start = time.time()
    response = session.post('https://api.curseforge.com/v1/fingerprints', headers=headers, json={
        "fingerprints": list(fingerprints.values())
    })
    print(f"curseforge took {time.time() - start}s")

    data = response.json()
    matches = data["data"]["exactFingerprints"]

    # result = {}
    # for filename, fingerprint in fingerprints.items():
    #     result[filename] = fingerprint in matches

    result = []
    for filename, fingerprint in fingerprints.items():
        if fingerprint in matches:
            result.append(filename)

    return result

def check_modrinth(session, filenames):
    hashes = {filename: get_sha1(filename) for filename in filenames}
    start = time.time()
    response = session.post("https://api.modrinth.com/v2/version_files", json={
        "hashes": list(hashes.values()),
        "algorithm": "sha1"
    })
    print(f"modrinth took {time.time() - start}s")

    data = response.json()
    # print(json.dumps(data, indent=4, sort_keys=True))
    # print(list(data.keys()))

    # result = {}
    # for filename, hash in hashes.items():
    #     result[filename] = hash in data

    result = []
    for filename, hash in hashes.items():
        if hash in data:
            result.append(filename)

    return result


RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
BLUE = "\033[34m"

session = requests.Session()

def check(session, directory="mods"):
    #TODO: add progressbar
    filepaths = [os.path.join(directory, filename) for filename in os.listdir(directory) if os.path.isfile(os.path.join(directory, filename))]
    modrinth_result = check_modrinth(session, filepaths)
    curseforge_result = check_curseforge(session, filepaths)

    for filepath in filepaths:
        status = f"{RED}could not find{RESET}"
        if filepath in modrinth_result and filepath in curseforge_result:
            status = f"{GREEN}found on both{RESET}"
        elif filepath in modrinth_result:
            status = f"{GREEN}found on modrinth{RESET}"
        elif filepath in curseforge_result:
            status = f"{GREEN}found on curseforge{RESET}"

        print(f"{BLUE}{filepath}{RESET}: {status}")

check(session, "mods")
