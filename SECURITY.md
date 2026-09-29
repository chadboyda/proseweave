# Security

## Reporting a vulnerability

Please report security problems privately, through GitHub's "Report a
vulnerability" button on the repository's Security tab (private vulnerability
reporting). Don't open a public issue. You should hear back within a week.

Include the version (`pip show proseweave`), what you ran, and what happened.
Never include your API key; revoke any key that was exposed.

## Supported versions

Security fixes go into the latest release only.

## What proseweave does with your data and key

- **Your text.** Without a key (`--no-jev`), everything runs locally and
  nothing leaves the machine. With a key, the parts of your text that need a
  judgement are sent to TypeSafe's Jev API (`https://api.typesafe.ai`) over
  HTTPS: individual sentences, sentence pairs, words, and for some easability
  properties the whole text. Don't analyse text you may not send to a third
  party.
- **Your key.** It is read from `TYPESAFE_API_KEY`, then
  `~/.config/proseweave/credentials` (written by `proseweave setup` with mode
  600), then `./.env`. It is sent only to the Jev API, in the `Authorization`
  header, and is never logged or cached.
- **The cache.** `PROSEWEAVE_CACHE`, when set, stores Jev answers on disk,
  keyed by a hash of each request. The cached answers can reveal what was
  asked, so treat the cache directory like the texts themselves.
- **Downloads.** The package downloads nothing at run time. The build scripts
  in `tools/` and `validation/` fetch their open inputs, and they are never run
  on install.
