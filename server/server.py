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


def build(
    type: str,
    script: Union[Path, str],
    cli_options=("--cf",),
    args=(),
    compressed=False,
):
    script = Path(script)
    command = [
        sys.executable,
        "-m",
        "opshin",
        *cli_options,
        "build",
        type,
        script,
        *args,
        "--recursion-limit",
        "2000",
        "-o",
        script.parent,
    ]
    subprocess.run(command)

    if compressed:
        built_contract = Path(f"{script.parent}/script.cbor")
        built_contract_compressed_cbor = Path(f"{script.parent}/tmp.cbor")

        with built_contract_compressed_cbor.open("wb") as fp:
            subprocess.run(["plutonomy-cli", built_contract, "--default"], stdout=fp)

        subprocess.run(
            [
                sys.executable,
                "-m",
                "uplc",
                "build",
                "--from-cbor",
                built_contract_compressed_cbor,
                "-o",
                f"{script.parent}/build",
                f"{script.parent}/build",
                "--recursion-limit",
                "2000",
            ]
        )


def lint(
    type: str,
    script: Union[Path, str],
    cli_options=("--cf",),
    args=(),
):
    script = Path(script)
    command = [
        sys.executable,
        "-m",
        "opshin",
        *cli_options,
        "lint",
        type,
        script,
        *args,
    ]
    linting_output_fp = script.parent / "linting_output.txt"

    # Run the command and save the output
    with open(linting_output_fp, "w") as f:
        subprocess.run(command, stdout=f)


@app.get("/opshin_version")
def get_opshin_version():
    return {"opshin_version": opshin.__version__}


@app.post("/compile")
async def compile_code(code_input: CodeInput):
    code_hash = hashlib.sha256(code_input.code.encode()).hexdigest()
    output_directory = f"builds/{code_hash}"
    if not Path(output_directory).exists():
        os.makedirs(output_directory)
        file_path = f"{output_directory}/validator.py"
        with open(file_path, "w") as file:
            file.write(code_input.code)
        try:
            lint("any", file_path)
            build("spending", file_path, compressed=False)
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail="Build process failed")

    linting_output_path = Path(output_directory) / "linting_output.txt"
    mainnet_addr_path = Path(output_directory) / "mainnet.addr"
    testnet_addr_path = Path(output_directory) / "testnet.addr"
    policy_id_path = Path(output_directory) / "script.policy_id"
    plutus_file_path = Path(output_directory) / "script.plutus"

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

    return {
        "linting_output": "".join(linting_output.split("/")[2:]),
        "mainnet_addr": mainnet_addr,
        "testnet_addr": testnet_addr,
        "policy_id": policy_id,
        "script_plutus": script_plutus,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
