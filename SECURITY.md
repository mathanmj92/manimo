# Security

Manimo runs on your own computer. Its local server listens on `127.0.0.1` only, checks a per-launch token and the Host header on every request, and takes its port exclusively. Code written by the AI assistant or pasted by you is scanned before it runs, and renders can be cancelled.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Email **mathannits92@gmail.com** with what you found and how to reproduce it. You will get a reply as soon as possible.

Useful to include: the Manimo version (Help, About), Windows version, and the steps.

## Keys and privacy

API keys entered in the app are stored encrypted on your PC. The assistant sends your request and code to the service you chose, and the app shows what is sent. Nothing else leaves your computer.
