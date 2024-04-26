from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import hashlib
import os
import sys
import subprocess
from pathlib import Path
from typing import Union

app = FastAPI()


class CodeInput(BaseModel):
    code: str


def build(type: str, script: Union[Path, str], cli_options=("--cf",), args=()):
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
    ]
    subprocess.run(command)

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
            f"{script.parent}/build_compressed",
            "--recursion-limit",
            "2000",
        ]
    )


@app.post("/compile")
async def compile_code(code_input: CodeInput):
    code_hash = hashlib.sha256(code_input.code.encode()).hexdigest()
    output_directory = f"builds/{code_hash}"
    os.makedirs(output_directory, exist_ok=True)
    file_path = f"{output_directory}/validator.py"
    with open(file_path, "w") as file:
        file.write(code_input.code)
    build("spending", file_path)

    return {"file_path": file_path}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
