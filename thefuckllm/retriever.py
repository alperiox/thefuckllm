"""Context retrieval from man pages, tldr, and cheat.sh."""

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
from fastembed import TextEmbedding


class ContextRetriever:
    """Retrieves and ranks context from man pages using semantic search."""

    def __init__(self, emb_model_name: str = "BAAI/bge-small-en-v1.5"):
        self._emb: TextEmbedding | None = None
        self._emb_model_name = emb_model_name

    @property
    def emb(self) -> TextEmbedding:
        """Lazy load embedding model."""
        if self._emb is None:
            self._emb = TextEmbedding(model_name=self._emb_model_name)
        return self._emb

    def get_content_with_tldr(self, cmd: str) -> str:
        """Gets the tldr page for a given command."""
        try:
            result = subprocess.run(
                f"tldr {cmd}", shell=True, capture_output=True, text=True, check=True
            )
            return "TLDR: \n\n" + result.stdout
        except subprocess.CalledProcessError:
            return ""

    def get_content_with_cheat_sh(self, cmd: str) -> str:
        """Gets cheat.sh content for a command."""
        try:
            response = requests.get(
                f"http://cheat.sh/{cmd}?T",
                timeout=10,
            )
            return "Cheat.sh: \n\n" + response.text if response.status_code == 200 else ""
        except requests.RequestException:
            return ""

    def get_all_sources_parallel(self, command: str) -> dict[str, str]:
        """Fetch man page, tldr, and cheat.sh in parallel."""
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.get_man, command): "man",
                executor.submit(self.get_content_with_tldr, command): "tldr",
                executor.submit(self.get_content_with_cheat_sh, command): "cheat",
            }
            results = {"man": "", "tldr": "", "cheat": ""}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    results[key] = future.result()
                except Exception:
                    results[key] = ""
        return results

    def get(
        self, command: str, query: str, top_k: int = 3, verbose: bool = False
    ) -> list[str]:
        """Gets the context for the given command and question query."""
        # Fetch all sources in parallel
        sources = self.get_all_sources_parallel(command)
        content = sources["man"]
        parsed_content = self.cleanup_text(self.parse_man_page(content))

        if not content:
            if verbose:
                print("couldn't find man page, falling back to cheat.sh + tldr")
            # Use already-fetched tldr and cheat.sh
            fallback = sources["tldr"] + sources["cheat"]
            return [fallback] if fallback else []

        if verbose:
            print(f"man_content: {content[:40]}")
            print(f"parsed_content: {parsed_content[:50] if parsed_content else 'empty'}")

        embeddings = np.vstack(list(self.emb.embed(parsed_content)))
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
        """Gets the man page for a given command."""
        try:
            result = subprocess.run(
                f"man {cmd} | col -b",
                shell=True,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""

    def parse_man_page(self, content: str) -> list[str]:
        """
        Parses a man page document and extracts each section separately.

        Args:
            content: the raw man page content as a string

        Returns:
            a list of section strings with their headers
        """
        if not content:
            return []

        sections = {}
        lines = content.split("\n")

        # pattern to match section headers (all uppercase words/letters at start of line)
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

    def cleanup_text(self, raw_man_content: list[str]) -> list[str]:
        """Clean up man page text."""
        return [s.replace("\t\t", " ") for s in raw_man_content]
