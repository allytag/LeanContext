# Security Incident Response

Furthermore, on-call must preserve exact identifiers from logs during the first incident timeline draft, because investigators compare these values directly with SIEM exports.

Record `AUTH_TOKEN_EXPIRED`, `RateLimitError`, and `2026-04-17T22:40:00Z` exactly as printed, including original capitalization and punctuation.

It's worth noting that responders should not rewrite stack traces, should not paraphrase exact error payloads, and should not sanitize API names during postmortem drafting.
