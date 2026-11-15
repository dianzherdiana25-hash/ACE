# ACE Home Access Note — the sandbox door (secret-free)

Recorded 2026-11-15 by Ian (main execution session). This note
contains NO credential values. Passwords and private keys never
travel in chat, files, or this repository (the repository is
public; vault discipline applies regardless).

## The door

- Host: `ace-sandbox.taild2ddcb.ts.net`, port **443**
  (TLS-proxied; the certificate is a valid Let's Encrypt cert
  for that name).
- Account: `sshremote` (uid 1002) on sandbox host
  `2887726280f4` (8 cores, ~24 GB RAM, 70 GB disk).
- Path: Tailscale Funnel endpoint → a dedicated restricted
  sshd on localhost:22222 (systemd unit `ssh-public.service`,
  config `/etc/ssh/sshd_config.public`, root-owned).
- `sshremote` holds sudo (ALL) in fresh sessions
  (owner-granted 2026-11-15).
- File transfer: `scp -O` (the restricted listener has no
  SFTP subsystem).

## Authentication state (2026-11-15) — FINAL arrangement

- **Password: the door's method, by design.** The public
  listener is password-only by the operator's deliberate
  security design, and it STAYS that way (hub decision
  2026-11-15): nobody flips it via sudo or by relay. The
  password value is held by the owner only — it is not
  recorded here or anywhere in this repository. The door
  was recovered on 2026-11-15: logins succeeded at 19:20
  and 19:23 WIB, were rejected around 20:57 WIB (a
  temporary lockout window), and succeeded again at
  ~21:47 WIB on a single ordered test.
- **Public key: installed account-side, for the main sshd
  route.** This environment's Ed25519 public key
  (fingerprint
  `SHA256:zxYrybwUM6iOslwPgzT6IfvIUx7JFahPGGGsOIZqJM8`) is in
  `~sshremote/.ssh/authorized_keys` (permissions 700/600,
  verified from inside). The main sshd (port 22) has
  `PubkeyAuthentication yes`, so the key is live for any
  direct route to that sshd. It does NOT authenticate
  through the public Funnel door, whose restricted
  listener offers **password only** (client debug:
  "Authentications that can continue: password"). A future
  reader must not mistake this for a key failure: the key
  is correctly installed; the Funnel listener is
  password-only by design. If the owner ever wants key
  auth through the Funnel, that is his direct word to the
  operator — not a change to make from inside.

## People

- Operator of the sandbox host: **kancuto** (Manus agent).
- Door coordination: ila (orchestrator) — Ian (main
  execution session) works through this door for ACE
  program execution in the sandbox home.

## Working clones in the home

- `/home/sshremote/ace-work-ian` — Ian's own clone of this
  repository (created 2026-11-15). Do not confuse with the
  custody tree `/workspace/ace-custody-lineage-guard` or
  the Antigravity line's active directories
  (`/workspace/ace-omega`, `/workspace/ACE`).
