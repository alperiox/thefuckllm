import subprocess
import re

from huggingface_hub import hf_hub_download

# uncomment if you want to use fastembed
from fastembed import TextEmbedding
import numpy as np

# llamacpp bindings
from llama_cpp import Llama

import requests
from platformdirs import user_cache_dir
import os


class ContextRetriever(object):
    def __init__(self, emb_model_name="BAAI/bge-small-en-v1.5"):
        self.emb = TextEmbedding(model_name=emb_model_name)

    def get_content_with_tldr(self, cmd: str) -> str:
        """gets the tldr page for a given command"""
        result = subprocess.run(
            f"tldr {cmd}", shell=True, capture_output=True, text=True, check=True
        )
        return "TLDR: \n\n" + result.stdout

    def get_content_with_cheat_sh(self, cmd: str) -> str:
        response = requests.get(
            f"http://cheat.sh/{cmd}?T",
        )
        return "Cheat.sh: \n\n" + response.text if response.status_code == 200 else ""

    def get(
        self, command: str, query: str, top_k: int = 3, verbose: bool = False
    ) -> list[str]:
        """gets the context for the given command and question query"""
        content = self.get_man(command)
        parsed_content = self.cleanup_text(self.parse_man_page(content))
        if not content:
            print("couldn't find man page, falling back to cheat.sh + tldr")
            parsed_content = self.get_content_with_tldr(
                command
            ) + self.get_content_with_cheat_sh(command)
            return [parsed_content]

        if verbose:
            print(f"man_content: {content[:40]}")
            print(f"parsed_content: {parsed_content[:50]}")

        embeddings = np.concatenate(list(self.emb.embed(parsed_content)))
        query_emb: np.ndarray = next(self.emb.embed(query))  # pyright: ignore

        if verbose:
            print(f"embeddings shape: {embeddings.shape}")
            print(f"query_emb shape: {query_emb.shape}")

        # simple cosine sim matching based on the embeddings
        norm = np.linalg.norm
        scores = (query_emb @ embeddings.T) / (
            norm(query_emb) * norm(embeddings, axis=1)
        )
        ixs = np.argsort(scores)
        retrieved_items = [parsed_content[k] for k in ixs[:top_k]]
        return retrieved_items

    def get_man(self, cmd: str) -> str:
        """gets the man page for a given command"""
        result = subprocess.run(
            f"man {cmd} | col -b",
            shell=True,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def parse_man_page(self, content: str) -> list[str]:
        """
        parses a man page document and extracts each section separately.

        Args:
            content: the raw man page content as a string

        Returns:
            a dictionary where keys are section names (e.g., 'NAME', 'SYNOPSIS')
            and values are the section contents
        """
        sections = {}
        lines = content.split("\n")

        # pattern to match section headers (all uppercase words/letters at start of line)
        # this matches lines that start with one or more uppercase letters, possibly with spaces
        section_pattern = re.compile(r"^([A-Z][A-Z\s]+)$")

        current_section: str | None = None
        current_content: list[str] = []

        # extract the header (first line typically contains the command name and manual section)
        if lines:
            header_match = re.match(r"^([A-Z]+\(\d+\))", lines[0])
            if header_match:
                sections["HEADER"] = lines[0].strip()

        for line in lines[1:]:  # skip the first line (header)
            # check if this line is a section header
            match = section_pattern.match(line.strip())

            if match:
                # save the previous section if it exists
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()

                # start a new section
                current_section = match.group(1).strip()
                current_content = []
            elif current_section:
                # add line to current section content
                current_content.append(line)

        # save the last section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return [k + "\n\n" + v for k, v in sections.items()]

    def cleanup_text(self, raw_man_content: list[str]):
        return [s.replace("\t\t", " ") for s in raw_man_content]


def download_models():
    cache_dir = user_cache_dir("thefuckllm")
    os.makedirs(cache_dir, exist_ok=True)

    if not os.path.exists(
        os.path.join(cache_dir, "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    ):
        print("Q4KM Qwen2.5-Coder-3b wasn't found, downloading!")
        q4km = hf_hub_download(
            repo_id="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
            filename="qwen2.5-coder-3b-instruct-q4_k_m.gguf",
            local_dir=cache_dir,
        )
    else:
        q4km = os.path.join(cache_dir, "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
        print("Q4KM - Ready to use!")

    if not os.path.exists(
        os.path.join(cache_dir, "qwen2.5-coder-3b-instruct-q8_0.gguf")
    ):
        print("Q8_0 Qwen2.5-Coder-3b wasn't found, downloading!")
        q8 = hf_hub_download(
            repo_id="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
            filename="qwen2.5-coder-3b-instruct-q8_0.gguf",
            local_dir=cache_dir,
        )
    else:
        q8 = os.path.join(cache_dir, "qwen2.5-coder-3b-instruct-q8_0.gguf")
        print("Q8 - Ready to use!")

    with open(os.path.join(cache_dir, "models.txt"), "w") as f:
        f.write(f"{q4km}\n{q8}")


if __name__ == "__main__":
    retriever = ContextRetriever()
    query = "how to set up a network and add it to a container in docker"
    download_models()
    cache_dir = user_cache_dir("thefuckllm")

    print("Loading the model...")
    llm = Llama(
        model_path=os.path.join(cache_dir, "qwen2.5-coder-3b-instruct-q8_0.gguf"),
        n_ctx=32768,
        n_gpu_layers=-1,
        verbose=False,
    )

    command_extraction_prompt = f"""<|im_start|>system
You're a simple tool name extractor, given the user query, extract the required cli tool's name. So if the query is about uv cli, then you should respond with simply uv, don't generate anything else and just tell the tool's name.
<|im_end|>
<|im_start|>user
Context:
{query}

Question: {query}
<|im_end|>
<|im_start|>assistant
"""
    command = llm(command_extraction_prompt, max_tokens=10, stop=["<|im_end|>"], echo=False) ['choices'][0]['text'] # pyright: ignore

    context = retriever.get(command, query)
    prompt = f"""<|im_start|>system
You are a CLI expert. Answer the user's question based strictly on the provided context.
Give a short, concise explanation and the exact command example.
<|im_end|>
<|im_start|>user
Context:
{context}

Question: {query}
<|im_end|>
<|im_start|>assistant
"""

    print("the answer...")
    output = llm(prompt, max_tokens=512, stop=["<|im_end|>"], echo=False)

    print(output["choices"][0]["text"])  # pyright: ignore
