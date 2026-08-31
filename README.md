# DialCoach
Python based ledger of buying signals, ties to the Hot/Warm/Cold scoring


### The one picture to keep in your head
The whole project is four things wired together, in this order: audio comes in, it gets turned into text, the text gets read by Claude, and everything gets saved to a local database.

The trick that makes this project pleasant to build and test is that none of the four pieces know about each other directly. The part that saves things to disk doesn't know if the text came from a real phone call or from a test pretending to be one.


# Dial Coach

A local, mostly-free phone-outreach call tracker.

Ties together local audio capture, speech-to-text transcription, a Claude
API agent (suggestions / playbook checks / summaries), a local SQLite
database, and a two-way sync with an existing Campaign_Tracker.xlsx.

See README.md for setup and docs/ARCHITECTURE.md for how the pieces fit
together. Every module that touches the outside world (audio hardware,
the Anthropic API, the filesystem) is written behind a small interface so
it can be exercised in tests without that dependency being present.