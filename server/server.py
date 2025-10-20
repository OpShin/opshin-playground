from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import hashlib
import os
import sys
import subprocess
from pathlib import Path
from typing import Union
import opshin

app = FastAPI()

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeInput(BaseModel):
    code: str
    compressed: bool = False


def build(
    script_name: Union[Path, str],
    output_path: Path,
    cli_options=(),
    args=(),
    compressed=False,
):
    command = [
        sys.executable,
        "-m",
        "opshin",
        *cli_options,
        "build",
        script_name,
        *args,
        "--recursion-limit",
        "4000",
    ]
    if compressed:
        command.append("-O3")
    res = subprocess.run(command, check=True, capture_output=True, cwd=output_path)
    return res.stdout.decode("utf-8"), res.stderr.decode("utf-8")



def lint(
    script: Union[Path, str],
    cli_options=(),
    args=(),
):
    script = Path(script)
    command = [
        sys.executable,
        "-m",
        "opshin",
        *cli_options,
        "lint",
        script,
        *args,
    ]
    linting_output_fp = script.parent / "linting_output.txt"

    # Run the command and save the output
    with open(linting_output_fp, "w") as f:
        subprocess.run(command, stdout=f, check=True)


@app.get("/opshin_version")
def get_opshin_version():
    return {"opshin_version": opshin.__version__}


@app.post("/compile")
async def compile_code(code_input: CodeInput):
    hash_input = f"{code_input.code}|compressed={code_input.compressed}".encode()
    code_hash = hashlib.sha256(hash_input).hexdigest()
    output_directory = f"builds/{code_hash}"
    if not Path(output_directory).exists():
        os.makedirs(output_directory)
        file_path = f"{output_directory}/validator.py"
        with open(file_path, "w") as file:
            file.write(code_input.code)
        try:
            lint(file_path)
            out = build(Path(file_path).name, output_path=Path(output_directory), compressed=code_input.compressed)
            print(out)
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail="Build process failed")

    linting_output_path = Path(output_directory) / "linting_output.txt"
    mainnet_addr_path = Path(output_directory) / "mainnet.addr"
    testnet_addr_path = Path(output_directory) / "testnet.addr"
    policy_id_path = Path(output_directory) / "script.policy_id"
    plutus_file_path = Path(output_directory) / "script.plutus"
    blueprint_file_path = Path(output_directory) / "blueprint.json"
    cbor_file_path = Path(output_directory) / "script.cbor"

    if not linting_output_path.exists():
        linting_output = ""
    else:
        with open(linting_output_path, "r") as file:
            linting_output = file.read().strip()

    if not mainnet_addr_path.exists():
        mainnet_addr = ""
    else:
        with open(mainnet_addr_path, "r") as file:
            mainnet_addr = file.read().strip()
    
    if not testnet_addr_path.exists():
        testnet_addr = ""
    else:
        with open(testnet_addr_path, "r") as file:
            testnet_addr = file.read().strip()
    
    if not policy_id_path.exists():
        policy_id = ""
    else:
        with open(policy_id_path, "r") as file:
            policy_id = file.read().strip()
    
    if not plutus_file_path.exists():
        script_plutus = ""
    else:
        with open(plutus_file_path, "r") as file:
            script_plutus = file.read()
    
    if not blueprint_file_path.exists():
        blueprint = ""
    else:
        with open(blueprint_file_path, "r") as file:
            blueprint = file.read()

    if not cbor_file_path.exists():
        cbor = ""
    else:
        with open(cbor_file_path, "rb") as file:
            cbor = file.read()

    return {
        "linting_output": "".join(linting_output.split("/")[2:]),
        "mainnet_addr": mainnet_addr,
        "testnet_addr": testnet_addr,
        "policy_id": policy_id,
        "script_plutus": script_plutus,
        "script_blueprint": blueprint,
        "script_cbor": cbor,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
