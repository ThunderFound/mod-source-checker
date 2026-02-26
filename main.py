import hashlib
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def get_sha1(filename):
    h = hashlib.sha1()
    with open(filename, 'rb') as file:
        while chunk := file.read(8192):
            h.update(chunk)
    return h.hexdigest()

def get_curseforge_fingerprint(filename: str):
    multiplex = 1540483477
    
    with open(filename, 'rb') as f:
        data = f.read()

    ignored_bytes = {9, 10, 13, 32}
    
    normalized = [b for b in data if b not in ignored_bytes]
    length = len(normalized)
    
    if length == 0:
        return 0

    hash_val = 1 ^ length 
    
    buffer = 0
    shift = 0
    
    def to_uint32(n):
        return n & 0xFFFFFFFF

    for b in normalized:
        buffer |= (b << shift)
        shift += 8
        
        if shift == 32:
            k = to_uint32(buffer * multiplex)
            k = to_uint32((k ^ (k >> 24)) * multiplex)
            hash_val = to_uint32(to_uint32(hash_val * multiplex) ^ k)
            
            buffer = 0
            shift = 0
            
    if shift > 0:
        hash_val = to_uint32((hash_val ^ buffer) * multiplex)
        
    hash_val = to_uint32((hash_val ^ (hash_val >> 13)) * multiplex)
    hash_val = to_uint32(hash_val ^ (hash_val >> 15))
    
    return hash_val
    
def check_curseforge(session, filenames):
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-api-key': os.getenv("CURSEFORGE_API_KEY")
    }

    fingerprints = {filename: get_curseforge_fingerprint(filename) for filename in filenames}
    response = session.post('https://api.curseforge.com/v1/fingerprints', headers=headers, json={
        "fingerprints": list(fingerprints.values())
    })

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
    response = session.post("https://api.modrinth.com/v2/version_files", json={
        "hashes": list(hashes.values()),
        "algorithm": "sha1"
    })

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
    #TODO: add progressbar and maybe other websites
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
