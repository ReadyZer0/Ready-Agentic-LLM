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
        "content": "what files are in the C:\\ drive?"
    },
    {
        "role": "assistant",
        "content": "~@terminal@~ dir C:\\ ~@exit@~\nHere are the files in your C:\\ drive."
    },
    {
        "role": "user",
        "content": "read the content of notes.md"
    },
    {
        "role": "assistant",
        "content": "~@read@~ notes.md ~@exit@~\nI have read notes.md."
    }
]
