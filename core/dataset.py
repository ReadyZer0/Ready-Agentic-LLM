"""
Synthetic Memory Dataset

Provides "few-shot" examples of perfect tool usage.
Injected into the session history at start so the model learns by example.
"""

SYNTHETIC_MEMORY = [
    {
        "role": "user",
        "content": "create a file called example.txt that says hello"
    },
    {
        "role": "assistant",
        "content": "~@write@~ example.txt\nhello\n~@exit@~\nI have created example.txt containing 'hello'."
    },
    {
        "role": "user",
        "content": "ask coder to create a simple python script to print hello world in app.py"
    },
    {
        "role": "assistant",
        "content": "~@delegate@~ Write a simple python script to print hello world in app.py ~@exit@~"
    },
    {
        "role": "user",
        "content": "[TOOL_RESULT: delegate]\n[CODER_RESPONSE]\nprint('hello world')"
    },
    {
        "role": "assistant",
        "content": "~@write@~ app.py\nprint('hello world')\n~@exit@~\nI have successfully received the code and saved it to app.py."
    }
]
