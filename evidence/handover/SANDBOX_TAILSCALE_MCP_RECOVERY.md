# Tailscale and MCP recovery

This note is for the persistent Sandbox hosting ACE. It does not change files under `/workspace/ACE`.

## After the Sandbox wakes

The `tailscaled` systemd service is enabled, uses userspace networking, and stores its device state under `/var/lib/tailscale`. It should resume when the Sandbox is running. Check it with:

```sh
sudo systemctl is-active tailscaled.service
sudo tailscale status
```

If Tailscale is not active or appears stuck after a wake, restart the service without logging out or deleting its state:

```sh
sudo systemctl restart tailscaled.service
sudo tailscale status
```

The device should show as `ace-sandbox`; use the current `100.x` address shown by `tailscale status`. Its present address is `100.93.61.37`. Tailnet policy still controls who may connect over Tailscale SSH. The Ubuntu login is `ubuntu`; from a Termux session already connected to the same tailnet, try:

```sh
ssh ubuntu@100.93.61.37
```

An actual SSH login has not yet been tested because no other tailnet peer was online when checked.

## MCP service

The MCP server is a separate enabled systemd service with automatic restart (`Restart=always`). Check it with:

```sh
sudo systemctl is-active sandbox-mcp.service
```

If needed, restart it with:

```sh
sudo systemctl restart sandbox-mcp.service
```

Its public endpoint remains `https://8765-ip7mlw9z5yxaw32doof4h-10c5b61c.sg3.manus.computer/mcp`. Keep the existing Bearer token; this note intentionally does not contain it.

A Sandbox that is suspended, deleted, or replaced cannot stay online. If it is replaced, inspect its Tailscale state and authorize the new device as needed; do not copy the old Tailscale state to it.
