#!/usr/bin/env python3
"""
simple script to chat with ollama server with streaming support and conversation memory.
"""

import sys
import json
from typing import List, Dict, Any
import requests


class OllamaChat:
    """handles conversation with ollama server with memory."""
    
    def __init__(self, server_url: str, model: str, system_prompt: str) -> None:
        """
        initialize the chat client.
        
        args:
            server_url: base url of the ollama server
            model: model name to use
            system_prompt: system prompt for the assistant
        """
        self.server_url: str = server_url
        self.model: str = model
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
    
    def add_user_message(self, content: str) -> None:
        """
        add a user message to the conversation history.
        
        args:
            content: user message content
        """
        self.messages.append({"role": "user", "content": content})
    
    def add_assistant_message(self, content: str) -> None:
        """
        add an assistant message to the conversation history.
        
        args:
            content: assistant message content
        """
        self.messages.append({"role": "assistant", "content": content})
    
    def stream_chat(self, user_message: str) -> str:
        """
        send a message and stream the response.
        
        args:
            user_message: the user's message
            
        returns:
            complete assistant response
        """
        # add user message to history
        self.add_user_message(user_message)
        
        # prepare request payload
        payload: Dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "messages": self.messages
        }
        
        # make streaming request
        try:
            response = requests.post(
                self.server_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=30
            )
            response.raise_for_status()
            
            # collect and print streamed response
            full_response: str = ""
            print("Assistant: ", end="", flush=True)
            
            for line in response.iter_lines():
                if line:
                    # decode the line
                    line_str = line.decode('utf-8')
                    
                    # skip if it's not json (some endpoints send "data: " prefix)
                    if line_str.startswith('data: '):
                        line_str = line_str[6:]
                    
                    try:
                        chunk: Dict[str, Any] = json.loads(line_str)
                        
                        # extract content from the chunk (format may vary by api)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                print(content, end="", flush=True)
                                full_response += content
                        
                        # check if stream is done
                        if chunk.get('choices', [{}])[0].get('finish_reason'):
                            break
                            
                    except json.JSONDecodeError:
                        # skip non-json lines
                        continue
            
            print()  # newline after response
            
            # add assistant response to history
            self.add_assistant_message(full_response)
            
            return full_response
            
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to ollama server: {e}", file=sys.stderr)
            return ""


def main() -> None:
    """main entry point."""
    # check if user provided a message
    if len(sys.argv) < 2:
        print("Usage: python ollama_chat.py '<your message>'")
        print("Example: python ollama_chat.py 'how to list files with sizes?'")
        sys.exit(1)
    
    # get user message from command line arguments
    user_message: str = ' '.join(sys.argv[1:])
    
    # configure ollama server
    server_url: str = "http://209.20.159.29:11434/v1/chat/completions"
    model: str = "qwen2.5-coder:3b"
    system_prompt: str = (
        "You're a senior developer that helps people with their questions. "
        "Your answers should be the simplest solution, concise, explanatory, and to the point. You don't have to present multiple solutions unless user specifically asks for it. The user is on the terminal, so python or any other programming language-specific  scripts wouldn't work. it should be bash or something similar"
    )
    
    # create chat instance
    chat = OllamaChat(server_url, model, system_prompt)
    
    # send message and get streaming response
    chat.stream_chat(user_message)
    
    # print conversation history summary
    print(f"\n[Conversation has {len(chat.messages) - 1} messages (excluding system)]")


if __name__ == "__main__":
    main()
